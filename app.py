from flask import Flask, render_template, request, jsonify, send_from_directory, session
from flask_cors import CORS
import os
import uuid
import hashlib
from datetime import datetime, timedelta
import json

app = Flask(__name__)
app.secret_key = 'localvoice-secret-key-2024'
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = 86400 * 30

CORS(app, supports_credentials=True)

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'mp4', 'mov'}

# Admin password - CHANGE THIS!
ADMIN_PASSWORD = 'admin123'

def load_data(filename, default=None):
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            return json.load(f)
    return default if default is not None else ([] if 's' in filename else {})

def save_data(filename, data):
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def get_user_by_id(user_id):
    users = load_data('users.json', {})
    for username, user_data in users.items():
        if user_data.get('id') == user_id:
            return user_data
    return None

def is_user_banned(username):
    users = load_data('users.json', {})
    if username in users:
        ban_info = users[username].get('ban', {})
        if ban_info.get('banned', False):
            ban_until = ban_info.get('until')
            if ban_until:
                if datetime.now().isoformat() < ban_until:
                    return True
                else:
                    # Ban expired
                    users[username]['ban']['banned'] = False
                    users[username]['ban']['until'] = None
                    save_data('users.json', users)
    return False

@app.route('/')
def index():
    if session.get('user_id'):
        user = get_user_by_id(session['user_id'])
        if user and is_user_banned(user['username']):
            session.clear()
            return render_template('banned.html')
        return render_template('feed.html')
    return render_template('landing.html')

@app.route('/login')
def login_page():
    return render_template('login.html')

@app.route('/register')
def register_page():
    return render_template('register.html')

@app.route('/banned')
def banned_page():
    return render_template('banned.html')

@app.route('/logout')
def logout():
    session.clear()
    return render_template('landing.html')

# Admin routes
@app.route('/admin')
def admin_login():
    return render_template('admin/login.html')

@app.route('/admin/dashboard')
def admin_dashboard():
    return render_template('admin/dashboard.html')

@app.route('/api/admin/login', methods=['POST'])
def admin_auth():
    data = request.json
    password = data.get('password', '')
    if password == ADMIN_PASSWORD:
        session['admin_logged_in'] = True
        return jsonify({'success': True})
    return jsonify({'success': False}), 401

@app.route('/api/admin/check')
def admin_check():
    if session.get('admin_logged_in'):
        return jsonify({'authenticated': True})
    return jsonify({'authenticated': False}), 401

@app.route('/api/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return jsonify({'success': True})

@app.route('/api/admin/users', methods=['GET'])
def get_all_users():
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    users = load_data('users.json', {})
    user_list = []
    for username, user_data in users.items():
        user_list.append({
            'username': username,
            'pseudonym': user_data['pseudonym'],
            'created_at': user_data['created_at'],
            'posts_count': user_data.get('posts_count', 0),
            'banned': user_data.get('ban', {}).get('banned', False),
            'ban_reason': user_data.get('ban', {}).get('reason', ''),
            'ban_until': user_data.get('ban', {}).get('until', None)
        })
    return jsonify(user_list)

@app.route('/api/admin/users/<username>/ban', methods=['POST'])
def ban_user(username):
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    duration = data.get('duration', 'permanent')  # '1h', '1d', '1w', '1m', 'permanent'
    reason = data.get('reason', 'No reason provided')
    
    users = load_data('users.json', {})
    
    if username not in users:
        return jsonify({'error': 'User not found'}), 404
    
    # Calculate ban until
    ban_until = None
    if duration != 'permanent':
        now = datetime.now()
        if duration == '1h':
            ban_until = (now + timedelta(hours=1)).isoformat()
        elif duration == '1d':
            ban_until = (now + timedelta(days=1)).isoformat()
        elif duration == '1w':
            ban_until = (now + timedelta(weeks=1)).isoformat()
        elif duration == '1m':
            ban_until = (now + timedelta(days=30)).isoformat()
    
    users[username]['ban'] = {
        'banned': True,
        'reason': reason,
        'until': ban_until,
        'banned_at': datetime.now().isoformat(),
        'banned_by': session.get('username', 'admin')
    }
    
    save_data('users.json', users)
    
    return jsonify({'message': f'User {username} banned successfully'})

@app.route('/api/admin/users/<username>/unban', methods=['POST'])
def unban_user(username):
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    users = load_data('users.json', {})
    
    if username not in users:
        return jsonify({'error': 'User not found'}), 404
    
    if 'ban' in users[username]:
        del users[username]['ban']
    
    save_data('users.json', users)
    
    return jsonify({'message': f'User {username} unbanned successfully'})

@app.route('/api/admin/users/<username>/reset-password', methods=['POST'])
def reset_user_password(username):
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    new_password = data.get('new_password', '')
    
    if len(new_password) < 4:
        return jsonify({'error': 'Password must be at least 4 characters'}), 400
    
    users = load_data('users.json', {})
    
    if username not in users:
        return jsonify({'error': 'User not found'}), 404
    
    users[username]['password'] = hash_password(new_password)
    save_data('users.json', users)
    
    return jsonify({'message': f'Password reset for {username}'})

@app.route('/api/admin/users/<username>/delete', methods=['DELETE'])
def delete_user(username):
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    users = load_data('users.json', {})
    
    if username not in users:
        return jsonify({'error': 'User not found'}), 404
    
    # Delete user's posts
    issues = load_data('issues.json', [])
    user_id = users[username]['id']
    issues = [i for i in issues if i.get('user_id') != user_id]
    save_data('issues.json', issues)
    
    # Delete user's comments
    comments = load_data('comments.json', {})
    for issue_id in comments:
        comments[issue_id] = [c for c in comments[issue_id] if c.get('user_id') != user_id]
    save_data('comments.json', comments)
    
    # Delete user
    del users[username]
    save_data('users.json', users)
    
    return jsonify({'message': f'User {username} deleted successfully'})

@app.route('/api/admin/stats', methods=['GET'])
def admin_stats():
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    users = load_data('users.json', {})
    issues = load_data('issues.json', [])
    comments = load_data('comments.json', {})
    
    total_comments = sum(len(c) for c in comments.values())
    banned_users = sum(1 for u in users.values() if u.get('ban', {}).get('banned', False))
    
    return jsonify({
        'total_users': len(users),
        'total_posts': len(issues),
        'total_comments': total_comments,
        'banned_users': banned_users,
        'total_likes': sum(i.get('likes', 0) for i in issues),
        'total_dislikes': sum(i.get('dislikes', 0) for i in issues),
        'total_shares': sum(i.get('shares', 0) for i in issues)
    })

# Regular user API routes
@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    
    if len(username) < 3:
        return jsonify({'error': 'Username must be at least 3 characters'}), 400
    if len(password) < 4:
        return jsonify({'error': 'Password must be at least 4 characters'}), 400
    
    users = load_data('users.json', {})
    if username in users:
        return jsonify({'error': 'Username already exists'}), 400
    
    user_id = str(uuid.uuid4())
    users[username] = {
        'id': user_id,
        'username': username,
        'password': hash_password(password),
        'created_at': datetime.now().isoformat(),
        'pseudonym': f"user_{user_id[:6]}",
        'posts_count': 0
    }
    save_data('users.json', users)
    return jsonify({'message': 'Registration successful'}), 201

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    
    users = load_data('users.json', {})
    
    if username not in users:
        return jsonify({'error': 'Invalid credentials'}), 401
    if users[username]['password'] != hash_password(password):
        return jsonify({'error': 'Invalid credentials'}), 401
    
    # Check if banned
    if is_user_banned(username):
        return jsonify({'error': 'Your account has been banned. Contact admin.'}), 403
    
    session['user_id'] = users[username]['id']
    session['username'] = username
    session.permanent = True
    
    return jsonify({'message': 'Login successful', 'username': username}), 200

@app.route('/api/check-auth')
def check_auth():
    if session.get('user_id'):
        user = get_user_by_id(session['user_id'])
        if user:
            if is_user_banned(user['username']):
                session.clear()
                return jsonify({'authenticated': False, 'banned': True})
            return jsonify({'authenticated': True, 'username': user['username']})
    return jsonify({'authenticated': False})

@app.route('/api/issues', methods=['GET'])
def get_issues():
    issues = load_data('issues.json', [])
    user_id = session.get('user_id')
    
    for issue in issues:
        if user_id:
            votes = issue.get('votes', {})
            issue['user_liked'] = votes.get(user_id) == 'like'
            issue['user_disliked'] = votes.get(user_id) == 'dislike'
            issue['user_shared'] = user_id in issue.get('shared_by', [])
        else:
            issue['user_liked'] = False
            issue['user_disliked'] = False
            issue['user_shared'] = False
        
        issue.pop('votes', None)
        issue.pop('shared_by', None)
        issue.pop('user_id', None)
    
    return jsonify(issues)

@app.route('/api/issues', methods=['POST'])
def create_issue():
    if not session.get('user_id'):
        return jsonify({'error': 'Please login'}), 401
    
    user = get_user_by_id(session['user_id'])
    if not user:
        return jsonify({'error': 'User not found'}), 401
    
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    location = request.form.get('location', '').strip()
    
    if not title or not description or not location:
        return jsonify({'error': 'All fields required'}), 400
    
    file_url = None
    file_type = None
    if 'image' in request.files:
        file = request.files['image']
        if file and file.filename:
            ext = file.filename.rsplit('.', 1)[1].lower()
            if ext in ALLOWED_EXTENSIONS:
                filename = f"{uuid.uuid4().hex}.{ext}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                file_url = f'/uploads/{filename}'
                file_type = 'image' if ext in {'png', 'jpg', 'jpeg', 'gif', 'webp'} else 'video'
    
    issue = {
        'id': str(uuid.uuid4()),
        'title': title,
        'description': description,
        'location': location,
        'timestamp': datetime.now().isoformat(),
        'pseudonym': user['pseudonym'],
        'likes': 0,
        'dislikes': 0,
        'shares': 0,
        'file_url': file_url,
        'file_type': file_type,
        'user_id': session['user_id'],
        'votes': {},
        'shared_by': []
    }
    
    issues = load_data('issues.json', [])
    issues.insert(0, issue)
    save_data('issues.json', issues)
    
    # Update user post count
    users = load_data('users.json', {})
    if user['username'] in users:
        users[user['username']]['posts_count'] = users[user['username']].get('posts_count', 0) + 1
        save_data('users.json', users)
    
    return jsonify(issue), 201

@app.route('/api/issues/<issue_id>/like', methods=['POST'])
def like_issue(issue_id):
    if not session.get('user_id'):
        return jsonify({'error': 'Please login'}), 401
    
    user_id = session['user_id']
    issues = load_data('issues.json', [])
    
    for issue in issues:
        if issue['id'] == issue_id:
            votes = issue.get('votes', {})
            current_vote = votes.get(user_id)
            
            if current_vote == 'like':
                issue['likes'] = max(0, issue['likes'] - 1)
                del votes[user_id]
                action = 'unliked'
            else:
                if current_vote == 'dislike':
                    issue['dislikes'] = max(0, issue['dislikes'] - 1)
                votes[user_id] = 'like'
                issue['likes'] = issue['likes'] + 1
                action = 'liked'
            
            issue['votes'] = votes
            save_data('issues.json', issues)
            
            return jsonify({
                'likes': issue['likes'],
                'dislikes': issue['dislikes'],
                'action': action
            })
    
    return jsonify({'error': 'Issue not found'}), 404

@app.route('/api/issues/<issue_id>/dislike', methods=['POST'])
def dislike_issue(issue_id):
    if not session.get('user_id'):
        return jsonify({'error': 'Please login'}), 401
    
    user_id = session['user_id']
    issues = load_data('issues.json', [])
    
    for issue in issues:
        if issue['id'] == issue_id:
            votes = issue.get('votes', {})
            current_vote = votes.get(user_id)
            
            if current_vote == 'dislike':
                issue['dislikes'] = max(0, issue['dislikes'] - 1)
                del votes[user_id]
                action = 'undisliked'
            else:
                if current_vote == 'like':
                    issue['likes'] = max(0, issue['likes'] - 1)
                votes[user_id] = 'dislike'
                issue['dislikes'] = issue['dislikes'] + 1
                action = 'disliked'
            
            issue['votes'] = votes
            save_data('issues.json', issues)
            
            return jsonify({
                'likes': issue['likes'],
                'dislikes': issue['dislikes'],
                'action': action
            })
    
    return jsonify({'error': 'Issue not found'}), 404

@app.route('/api/issues/<issue_id>/share', methods=['POST'])
def share_issue(issue_id):
    if not session.get('user_id'):
        return jsonify({'error': 'Please login'}), 401
    
    user_id = session['user_id']
    issues = load_data('issues.json', [])
    
    for issue in issues:
        if issue['id'] == issue_id:
            shared_by = issue.get('shared_by', [])
            
            if user_id not in shared_by:
                shared_by.append(user_id)
                issue['shares'] = issue.get('shares', 0) + 1
                issue['shared_by'] = shared_by
                save_data('issues.json', issues)
                already_shared = False
            else:
                already_shared = True
            
            share_url = f"{request.host_url}post/{issue_id}"
            
            return jsonify({
                'shares': issue['shares'],
                'share_url': share_url,
                'already_shared': already_shared
            })
    
    return jsonify({'error': 'Issue not found'}), 404

@app.route('/api/issues/<issue_id>/comments', methods=['GET'])
def get_comments(issue_id):
    comments = load_data('comments.json', {})
    return jsonify(comments.get(issue_id, []))

@app.route('/api/issues/<issue_id>/comments', methods=['POST'])
def add_comment(issue_id):
    if not session.get('user_id'):
        return jsonify({'error': 'Please login'}), 401
    
    user = get_user_by_id(session['user_id'])
    if not user:
        return jsonify({'error': 'User not found'}), 401
    
    data = request.json
    comment_text = data.get('comment', '').strip()
    
    if not comment_text:
        return jsonify({'error': 'Comment cannot be empty'}), 400
    
    comments = load_data('comments.json', {})
    
    if issue_id not in comments:
        comments[issue_id] = []
    
    comment = {
        'id': str(uuid.uuid4()),
        'text': comment_text,
        'pseudonym': user['pseudonym'],
        'user_id': session['user_id'],
        'timestamp': datetime.now().isoformat()
    }
    
    comments[issue_id].append(comment)
    save_data('comments.json', comments)
    
    return jsonify(comment), 201

@app.route('/post/<issue_id>')
def view_post(issue_id):
    issues = load_data('issues.json', [])
    for issue in issues:
        if issue['id'] == issue_id:
            return render_template('single_post.html', post=issue)
    return "Post not found", 404

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
