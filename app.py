from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import json
import os
from datetime import datetime
import requests
from flask_apscheduler import APScheduler
import logging
from logging.handlers import RotatingFileHandler
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect
import shutil

app = Flask(__name__)

# Generate a strong key or load from env
import secrets
app.secret_key = os.environ.get('SECRET_KEY') or secrets.token_hex(32)

# Security Configuration
csrf = CSRFProtect(app)
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

# Logging Configuration
if not os.path.exists('logs'):
    os.mkdir('logs')
handler = RotatingFileHandler('logs/mitce.log', maxBytes=10000, backupCount=1)
handler.setLevel(logging.INFO)
app.logger.addHandler(handler)
app.logger.setLevel(logging.INFO)
app.logger.info('NekoCloud startup')

CONFIG_FILE = 'config.json'

def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        app.logger.error(f"Error loading config: {e}")
        return {}

def save_config(config):
    try:
        # Create backup
        if os.path.exists(CONFIG_FILE):
            shutil.copy(CONFIG_FILE, CONFIG_FILE + '.bak')
            
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        app.logger.error(f"Error saving config: {e}")
        return False

def fetch_subscription_info(url):
    """
    Fetches subscription info from the given URL.
    Tries HEAD first, then GET (stream=True).
    Parses 'Subscription-Userinfo' header.
    """
    try:
        app.logger.info(f"Fetching subscription info from: {url}")
        headers = {'User-Agent': 'Clash/1.0'}
        
        response = None
        try:
            response = requests.head(url, headers=headers, timeout=10)
        except requests.exceptions.RequestException:
            app.logger.info("HEAD request failed, trying GET...")
            try:
                response = requests.get(url, headers=headers, timeout=15, stream=True)
            except requests.exceptions.RequestException as e:
                app.logger.error(f"GET request failed: {e}")
                return None

        if not response:
            return None

        info = {}
        user_info = None
        
        # Case-insensitive header lookup
        for k, v in response.headers.items():
            if 'subscription-userinfo' in k.lower():
                user_info = v
                break
                
        if user_info:
            parts = {}
            for p in user_info.split(';'):
                if '=' in p:
                    k, v = p.split('=', 1)
                    parts[k.strip()] = v.strip()
            
            if 'total' in parts:
                try:
                    total_bytes = int(parts['total'])
                    info['total'] = f"{total_bytes / 1024**3:.2f} GB"
                except ValueError: pass
                
            if 'download' in parts and 'upload' in parts:
                try:
                    used_bytes = int(parts['download']) + int(parts['upload'])
                    info['used'] = f"{used_bytes / 1024**3:.2f} GB"
                except ValueError: pass
                
            if 'expire' in parts:
                try:
                    expire_timestamp = int(parts['expire'])
                    dt = datetime.fromtimestamp(expire_timestamp)
                    info['expire'] = dt.strftime('%Y-%m-%d')
                except ValueError:
                    info['expire'] = "无限期"
        else:
            app.logger.warning(f"No Subscription-Userinfo header found for {url}")
            
        return info
    except Exception as e:
        app.logger.error(f"Error in fetch_subscription_info: {e}")
        return None

# Scheduler
class Config:
    SCHEDULER_API_ENABLED = True

app.config.from_object(Config())
scheduler = APScheduler()

def scheduled_refresh_task():
    app.logger.info("Executing scheduled traffic refresh task...")
    with app.app_context():
        config = load_config()
        updated = False
        
        # Refresh Optimized
        url_opt = config.get('fetch_info_url_opt')
        if url_opt:
            info = fetch_subscription_info(url_opt)
            if info:
                if 'total' in info: config['traffic_total_opt'] = info['total']
                if 'used' in info: config['traffic_used_opt'] = info['used']
                if 'expire' in info: config['expiration_date_opt'] = info['expire']
                updated = True
                
        # Refresh Residential
        url_res = config.get('fetch_info_url_res')
        if url_res:
            info = fetch_subscription_info(url_res)
            if info:
                if 'total' in info: config['traffic_total_res'] = info['total']
                if 'used' in info: config['traffic_used_res'] = info['used']
                if 'expire' in info: config['expiration_date_res'] = info['expire']
                updated = True
        
        if updated:
            save_config(config)
            app.logger.info("Scheduled task updated traffic info.")

scheduler.add_job(id='daily_refresh', func=scheduled_refresh_task, trigger='cron', hour=0, minute=0)
scheduler.init_app(app)
scheduler.start()

def parse_traffic(traffic_str):
    """Parses traffic string (e.g., '1.5 GB', '500 MB') to bytes."""
    if not traffic_str:
        return 0.0
    
    try:
        parts = traffic_str.split()
        if len(parts) < 2:
            return float(parts[0]) # Assume bytes if no unit
            
        value = float(parts[0])
        unit = parts[1].upper()
        
        factors = {
            'B': 1,
            'KB': 1024,
            'MB': 1024**2,
            'GB': 1024**3,
            'TB': 1024**4
        }
        
        return value * factors.get(unit, 1)
    except Exception:
        return 0.0

@app.template_filter('traffic_percent')
def traffic_percent_filter(used_str, total_str):
    """Calculates percentage based on traffic strings."""
    used_bytes = parse_traffic(used_str)
    total_bytes = parse_traffic(total_str)
    
    if total_bytes <= 0:
        return 0
        
    percent = (used_bytes / total_bytes) * 100
    return min(percent, 100) # Cap at 100%

# Routes
@app.route('/')
def index():
    if 'user_logged_in' in session:
        return redirect(url_for('dashboard'))
    if 'admin_logged_in' in session:
        return redirect(url_for('admin_dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        config = load_config()
        
        if username == config.get('admin_username') and password == config.get('admin_password'):
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        elif username == config.get('user_username') and password == config.get('user_password'):
            session['user_logged_in'] = True
            return redirect(url_for('dashboard'))
        else:
            flash('用户名或密码错误', 'danger')
            
    return render_template('login.html', config=load_config())

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'user_logged_in' not in session and 'admin_logged_in' not in session:
        return redirect(url_for('login'))
    
    config = load_config()
    return render_template('dashboard.html', config=config, rules_agreed=session.get('rules_agreed', False))

@app.route('/get_subscription/<line_type>')
def get_subscription(line_type):
    if 'user_logged_in' not in session and 'admin_logged_in' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    # Check if user agreed to rules
    if not session.get('rules_agreed'):
        return jsonify({'redirect': url_for('rules')})
        
    config = load_config()
    link = ""
    if line_type == 'opt':
        link = config.get('sub_link_optimized')
    elif line_type == 'res':
        link = config.get('sub_link_residential')
    else:
        return jsonify({'error': 'Invalid line type'}), 400
        
    return jsonify({'link': link})

@app.route('/rules')
def rules():
    if 'user_logged_in' not in session and 'admin_logged_in' not in session:
        return redirect(url_for('login'))
    return render_template('rules.html', config=load_config())

@app.route('/agree_rules', methods=['POST'])
def agree_rules():
    if 'user_logged_in' not in session and 'admin_logged_in' not in session:
        return redirect(url_for('login'))
    
    session['rules_agreed'] = True
    flash('您已同意服务条款，现在可以获取订阅链接。', 'success')
    return redirect(url_for('dashboard'))

@app.route('/refresh_traffic', methods=['POST'])
def user_refresh_traffic():
    if 'user_logged_in' not in session and 'admin_logged_in' not in session:
        return redirect(url_for('login'))
    
    # Trigger the same logic as the scheduled task
    scheduled_refresh_task()
    flash('流量信息刷新请求已发送，请查看最新数据。', 'success')
    return redirect(url_for('dashboard'))

@app.route('/admin', methods=['GET', 'POST'])
def admin_dashboard():
    if 'admin_logged_in' not in session:
        return redirect(url_for('login'))
        
    config = load_config()
    
    if request.method == 'POST':
        # Site Config
        config['site_title'] = request.form.get('site_title')
        config['announcement'] = request.form.get('announcement')
        
        # Sync URLs
        config['fetch_info_url_opt'] = request.form.get('fetch_info_url_opt')
        config['fetch_info_url_res'] = request.form.get('fetch_info_url_res')
        
        # Display Links
        config['sub_link_optimized'] = request.form.get('sub_link_optimized')
        config['sub_link_residential'] = request.form.get('sub_link_residential')
        
        # Optimized Line Data (Manual)
        config['traffic_total_opt'] = request.form.get('traffic_total_opt')
        config['traffic_used_opt'] = request.form.get('traffic_used_opt')
        config['expiration_date_opt'] = request.form.get('expiration_date_opt')
        
        # Residential Line Data (Manual)
        config['traffic_total_res'] = request.form.get('traffic_total_res')
        config['traffic_used_res'] = request.form.get('traffic_used_res')
        config['expiration_date_res'] = request.form.get('expiration_date_res')
        
        # Common
        config['speed_limit'] = request.form.get('speed_limit')
        config['status'] = request.form.get('status')
        config['user_role'] = request.form.get('user_role')
        
        # Line Details
        config['line_opt_name'] = request.form.get('line_opt_name')
        config['line_opt_desc'] = request.form.get('line_opt_desc')
        config['line_res_name'] = request.form.get('line_res_name')
        config['line_res_desc'] = request.form.get('line_res_desc')
        config['res_protocol'] = request.form.get('res_protocol')
        
        # Text Areas
        config['rules_text'] = request.form.get('rules_text')
        config['disclaimer_text'] = request.form.get('disclaimer_text')
        
        # Downloads
        for key in ['dl_ios_stable', 'dl_ios_beta', 'dl_android_stable', 'dl_android_beta', 
                   'dl_windows_stable', 'dl_macos_stable', 'dl_linux_stable', 'dl_tv_stable']:
            config[key] = request.form.get(key)
            
        # Accounts
        config['user_username'] = request.form.get('user_username')
        config['user_password'] = request.form.get('user_password')
        config['admin_password'] = request.form.get('admin_password')
        
        if save_config(config):
            flash('配置已保存！', 'success')
        else:
            flash('保存失败，请查看日志。', 'danger')
            
        return redirect(url_for('admin_dashboard'))
        
    return render_template('admin.html', config=config)

@app.route('/admin/refresh_info', methods=['POST'])
def refresh_info():
    if 'admin_logged_in' not in session:
        return redirect(url_for('login'))
        
    config = load_config()
    updated = False
    
    # Check specific buttons
    # Note: In the form, buttons should have name="action" or similar to distinguish,
    # OR we check if the input field associated with it has value if we were submitting just that part.
    # But here we are submitting the whole form or specific inputs.
    # Let's check which URL was intended. 
    # Ideally, the form action should be specific or carry a parameter.
    # For simplicity, we'll try to sync BOTH if the URLs are present in the form data or config,
    # OR we can just run the scheduled task logic immediately.
    
    # Let's rely on the hidden input or button value if possible, but standard 'formaction' sends the form.
    # We will try to update from the input fields in the request if present.
    
    fetch_url_opt = request.form.get('fetch_info_url_opt')
    if fetch_url_opt:
        info = fetch_subscription_info(fetch_url_opt)
        if info:
            if 'total' in info: config['traffic_total_opt'] = info['total']
            if 'used' in info: config['traffic_used_opt'] = info['used']
            if 'expire' in info: config['expiration_date_opt'] = info['expire']
            config['fetch_info_url_opt'] = fetch_url_opt
            updated = True
            
    fetch_url_res = request.form.get('fetch_info_url_res')
    if fetch_url_res:
        info = fetch_subscription_info(fetch_url_res)
        if info:
            if 'total' in info: config['traffic_total_res'] = info['total']
            if 'used' in info: config['traffic_used_res'] = info['used']
            if 'expire' in info: config['expiration_date_res'] = info['expire']
            config['fetch_info_url_res'] = fetch_url_res
            updated = True
            
    if updated:
        save_config(config)
        flash('流量信息同步成功！', 'success')
    else:
        flash('未能更新信息，请检查链接是否有效。', 'warning')
        
    return redirect(url_for('admin_dashboard'))

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500

if __name__ == '__main__':
    # Production settings
    # For actual production, use a WSGI server like gunicorn or waitress
    app.run(host='0.0.0.0', port=5001, debug=False)
