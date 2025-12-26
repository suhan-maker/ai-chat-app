import os
import sqlite3
import json
import datetime
from flask import Flask, request, session, redirect, url_for, render_template, flash, Response, stream_with_context
from werkzeug.security import generate_password_hash, check_password_hash
import google.generativeai as genai
import stripe
import numpy as np

# Configure APIs
genai.configure(api_key=os.environ.get('GENAI_API_KEY'))
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')
STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY')

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'your_secret_key_here')

# Database path
DB_PATH = 'db/suhan_ai.db'

# Initialize database
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        subscription_plan TEXT DEFAULT 'free',
        stripe_customer_id TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    # Conversations table
    c.execute('''CREATE TABLE IF NOT EXISTS conversations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )''')
    # Messages table
    c.execute('''CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        conversation_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (conversation_id) REFERENCES conversations (id),
        FOREIGN KEY (user_id) REFERENCES users (id)
    )''')
    # Memories table
    c.execute('''CREATE TABLE IF NOT EXISTS memories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        content TEXT NOT NULL,
        embedding TEXT NOT NULL,  -- JSON list of floats
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )''')
    # Daily usage table
    c.execute('''CREATE TABLE IF NOT EXISTS daily_usage (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        message_count INTEGER DEFAULT 0,
        FOREIGN KEY (user_id) REFERENCES users (id),
        UNIQUE(user_id, date)
    )''')
    conn.commit()
    conn.close()

init_db()

# Helper functions
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def cosine_similarity(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

def get_relevant_memories(user_id, query_embedding, top_k=5):
    conn = get_db()
    memories = conn.execute('SELECT content, embedding FROM memories WHERE user_id = ?', (user_id,)).fetchall()
    conn.close()
    similarities = []
    for mem in memories:
        emb = json.loads(mem['embedding'])
        sim = cosine_similarity(query_embedding, emb)
        similarities.append((sim, mem['content']))
    similarities.sort(reverse=True, key=lambda x: x[0])
    return [content for _, content in similarities[:top_k]]

def check_daily_limit(user_id):
    today = datetime.date.today().isoformat()
    conn = get_db()
    usage = conn.execute('SELECT message_count FROM daily_usage WHERE user_id = ? AND date = ?', (user_id, today)).fetchone()
    conn.close()
    if usage:
        return usage['message_count'] < 10  # Free limit
    return True

def increment_usage(user_id):
    today = datetime.date.today().isoformat()
    conn = get_db()
    conn.execute('INSERT OR IGNORE INTO daily_usage (user_id, date, message_count) VALUES (?, ?, 0)', (user_id, today))
    conn.execute('UPDATE daily_usage SET message_count = message_count + 1 WHERE user_id = ? AND date = ?', (user_id, today))
    conn.commit()
    conn.close()

# Routes
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('chat'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        password_hash = generate_password_hash(password)
        conn = get_db()
        try:
            conn.execute('INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)', (username, email, password_hash))
            conn.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username or email already exists.', 'error')
        finally:
            conn.close()
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['plan'] = user['subscription_plan']
            return redirect(url_for('chat'))
        flash('Invalid credentials.', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/chat', methods=['GET', 'POST'])
def chat():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    plan = session['plan']
    conversation_id = request.args.get('conv_id')
    if not conversation_id:
        # Create new conversation
        conn = get_db()
        conn.execute('INSERT INTO conversations (user_id, title) VALUES (?, ?)', (user_id, 'New Chat'))
        conversation_id = conn.lastrowid
        conn.commit()
        conn.close()
    if request.method == 'POST':
        if plan == 'free' and not check_daily_limit(user_id):
            return Response('Daily limit exceeded.', status=429)
        user_message = request.form['message']
        increment_usage(user_id)
        # Get relevant memories
        query_emb = genai.embed_content(model='models/embedding-001', content=user_message)['embedding']
        memories = get_relevant_memories(user_id, query_emb)
        context = '\n'.join(memories) if memories else ''
        prompt = f"Context from previous interactions:\n{context}\n\nUser: {user_message}\nAI:"
        # Store user message
        conn = get_db()
        conn.execute('INSERT INTO messages (conversation_id, user_id, role, content) VALUES (?, ?, ?, ?)', (conversation_id, user_id, 'user', user_message))
        conn.commit()
        conn.close()
        # Stream response
        def generate():
            try:
                response = genai.GenerativeModel('gemini-1.5-flash').generate_content(prompt, stream=True)
                full_response = ''
                for chunk in response:
                    if chunk.text:
                        full_response += chunk.text
                        yield f"data: {json.dumps({'text': chunk.text})}\n\n"
                yield "data: [DONE]\n\n"
                # Store AI response and memory
                conn = get_db()
                conn.execute('INSERT INTO messages (conversation_id, user_id, role, content) VALUES (?, ?, ?, ?)', (conversation_id, user_id, 'ai', full_response))
                # Store memory
                mem_emb = genai.embed_content(model='models/embedding-001', content=user_message + ' ' + full_response)['embedding']
                conn.execute('INSERT INTO memories (user_id, content, embedding) VALUES (?, ?, ?)', (user_id, user_message + ' ' + full_response, json.dumps(mem_emb)))
                conn.commit()
                conn.close()
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
        return Response(stream_with_context(generate()), mimetype='text/event-stream')
    # Get messages
    conn = get_db()
    messages = conn.execute('SELECT role, content FROM messages WHERE conversation_id = ? ORDER BY timestamp', (conversation_id,)).fetchall()
    conversations = conn.execute('SELECT id, title FROM conversations WHERE user_id = ? ORDER BY created_at DESC', (user_id,)).fetchall()
    conn.close()
    return render_template('chat.html', messages=messages, conversations=conversations, current_conv=conversation_id, plan=plan)

@app.route('/billing')
def billing():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('billing.html', stripe_key=STRIPE_PUBLISHABLE_KEY)

@app.route('/create-checkout-session', methods=['POST'])
def create_checkout_session():
    if 'user_id' not in session:
        return {'error': 'Not logged in'}, 401
    user_id = session['user_id']
    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {'name': 'Pro Plan'},
                    'unit_amount': 999,  # $9.99
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=url_for('chat', _external=True) + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=url_for('billing', _external=True),
        )
        return {'id': checkout_session.id}
    except Exception as e:
        return {'error': str(e)}, 400

@app.route('/webhook', methods=['POST'])
def stripe_webhook():
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get('stripe-signature')
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, os.environ.get('STRIPE_WEBHOOK_SECRET'))
    except ValueError:
        return 'Invalid payload', 400
    except stripe.error.SignatureVerificationError:
        return 'Invalid signature', 400
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        # Update user plan
        conn = get_db()
        conn.execute('UPDATE users SET subscription_plan = ? WHERE id = ?', ('pro', session['metadata']['user_id'] if 'user_id' in session else 1))  # Assume
        conn.commit()
        conn.close()
    return '', 200

# For PythonAnywhere WSGI
application = app

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)