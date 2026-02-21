import os
import sys
import shutil
import uuid
from flask import Flask, request, jsonify, send_from_directory, session, redirect, send_file, make_response
from functools import wraps
from dotenv import load_dotenv
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import unquote
from werkzeug.utils import secure_filename
import smtplib
from email.mime.text import MIMEText
import threading

# Ensure the backend directory is in the python path for Vercel
backend_dir = os.path.dirname(__file__)
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

from db import get_supabase_client
from pricing import calculate_total

# Load .env (local only)
env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
if os.path.exists(env_path):
    load_dotenv(env_path)

app = Flask(__name__, static_folder="../static", template_folder="../shopkeeper")

# Secret key for sessions
app.secret_key = os.environ.get("SECRET_KEY", "super_secret_shopkeeper_key")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASS", "admin123")
TEMP_SECURE_DIR = '/tmp/secure_temp' if os.environ.get('VERCEL_ENV') else os.path.join(app.root_path, '../secure_temp')
try:
    os.makedirs(TEMP_SECURE_DIR, exist_ok=True)
except Exception as e:
    print(f"Warning: Could not create temp dir: {e}")

# Security configurations
IS_PRODUCTION = os.environ.get('VERCEL_ENV') == 'production'
app.config['SESSION_COOKIE_SECURE'] = IS_PRODUCTION  # HTTPS only in production
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1 hour
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 # 16MB Limit for uploads

# Add security headers to all responses
@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Content-Security-Policy'] = (
    "frame-ancestors 'self' https://*.supabase.co"
)

    if 'Access-Control-Allow-Origin' not in response.headers:
        response.headers['Access-Control-Allow-Origin'] = 'http://127.0.0.1:5001'
    return response


# Decorator: Login Required
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            if request.path.startswith('/api/'):
                return jsonify({"error": "Unauthorized"}), 401
            return redirect('/admin/login')
        return f(*args, **kwargs)
    return decorated_function

# --- Shopkeeper Routes ---

# --- Dynamic Routing ---

@app.route('/')
def index():
    site_type = os.environ.get("SITE_TYPE", "ADMIN")
    if site_type == "CUSTOMER":
        return send_from_directory('../customer', 'index.html')
    return redirect('/admin')

@app.route('/<path:path>')
def serve_root_files(path):
    # This serves files like options.html or checkout.html from the correct folder
    # based on the SITE_TYPE environment variable.
    site_type = os.environ.get("SITE_TYPE", "ADMIN")
    
    if site_type == "CUSTOMER":
        return send_from_directory('../customer', path)
    
    # Default for Admin
    if path.startswith('admin/'):
         return send_from_directory('../shopkeeper', path.replace('admin/', ''))
    
    return send_from_directory('../shopkeeper', path)

@app.route('/customer')
def customer_index():
    return send_from_directory('../customer', 'index.html')

@app.route('/admin')
@login_required
def admin_dashboard():
    site_type = os.environ.get("SITE_TYPE", "ADMIN")
    if site_type == "CUSTOMER":
        return jsonify({"error": "Forbidden: Cannot access Admin dashboard from the Customer Portal."}), 403
    return send_from_directory('../shopkeeper', 'dashboard.html')

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    site_type = os.environ.get("SITE_TYPE", "ADMIN")
    if site_type == "CUSTOMER":
        return jsonify({"error": "Forbidden: Cannot access Admin panel from the Customer Portal."}), 403

    if request.method == 'GET':
        if session.get('logged_in'):
             return redirect('/admin')
        return send_from_directory('../shopkeeper', 'login.html')
        
    data = request.json
    if data.get('password') == ADMIN_PASSWORD:
        session['logged_in'] = True
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Invalid Password"}), 401

@app.route('/admin/logout', methods=['POST'])
def admin_logout():
    session.clear()
    return jsonify({"success": True})

@app.route('/admin/logged-out')
def admin_logged_out():
    return send_from_directory('../shopkeeper', 'logout.html')

# Serve Shopkeeper Pages
@app.route('/shopkeeper/<path:path>')
@login_required
def serve_shop_pages(path):
    response = make_response(send_from_directory('../shopkeeper', path))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return response

# Serve Shared Static Assets (CSS/JS)
@app.route('/static/<path:path>')
def serve_static(path):
    return send_from_directory('../static', path)

# --- API Endpoints ---

@app.route('/api/shop/stats', methods=['GET'])
@login_required
def get_shop_stats():
    try:
        supabase = get_supabase_client()
        
        # 1. Pending Prints
        res_pending = supabase.client.table('orders').select('id', count='exact').neq('order_status', 'COMPLETED').execute()
        count_pending = res_pending.count if res_pending.count is not None else len(res_pending.data)
        
        # 2. UPI Verification
        res_verify = supabase.client.table('orders').select('id', count='exact').eq('payment_status', 'PENDING_VERIFICATION').execute()
        count_verify = res_verify.count if res_verify.count is not None else len(res_verify.data)
        
        # 3. Today's Revenue
        ist_offset = timezone(timedelta(hours=5, minutes=30))
        now_ist = datetime.now(ist_offset)
        start_of_day_ist = now_ist.replace(hour=0, minute=0, second=0, microsecond=0)
        start_of_day_utc = start_of_day_ist.astimezone(timezone.utc)
        
        res_revenue = supabase.client.table('orders')\
            .select('total_amount')\
            .eq('payment_status', 'PAID')\
            .gte('created_at', start_of_day_utc.isoformat())\
            .execute()
            
        revenue = sum((item.get('total_amount') or 0) for item in (res_revenue.data or []))
        
        return jsonify({
            "pending_print": count_pending,
            "upi_verify": count_verify,
            "revenue_today": revenue
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def send_notification_email_async(order_data):
    try:
        sender_email = os.environ.get("SMTP_EMAIL")
        sender_password = os.environ.get("SMTP_PASSWORD")
        receiver_email = os.environ.get("RECEIVER_EMAIL", "kalpanav856@gmail.com")

        if not sender_email or not sender_password:
            return

        msg_body = f"""New Print Order Received!

Customer: {order_data.get('customer_name')}
Phone: {order_data.get('customer_phone')}
File: {order_data.get('file_name')}
Pages: {order_data.get('pages')}, Copies: {order_data.get('copies')}
Options: {order_data.get('print_color')}, {order_data.get('print_sides')}
Total Amount: ₹{order_data.get('total_amount')}
Payment: {order_data.get('payment_method')} ({order_data.get('payment_status')})

Please check your dashboard to process the order.
Link: https://barath-printing-app.vercel.app/
"""
        msg = MIMEText(msg_body)
        msg['Subject'] = f"New Order - {order_data.get('customer_name')} (₹{order_data.get('total_amount')})"
        msg['From'] = sender_email
        msg['To'] = receiver_email

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(sender_email, sender_password)
            smtp.send_message(msg)
    except Exception as e:
        print(f"Failed to send email notification: {e}")

def notify_shop(order_data):
    send_notification_email_async(order_data)

@app.route('/api/create-order', methods=['POST'])
def create_order():
    data = request.json
    
    # 1. Consent Enforcement
    if not data.get('accepted_terms'):
        return jsonify({"error": "You must accept the Terms & Conditions and Privacy Policy to proceed."}), 400

    # 2. Metadata Capture
    ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
    user_agent = request.headers.get('User-Agent')
    accepted_at = datetime.now(timezone.utc).isoformat()
    
    # 3. Rate Limiting (Simple IP based)
    try:
        supabase = get_supabase_client()
        # Check last order from this IP
        last_order = supabase.client.table('orders').select('created_at').eq('ip_address', ip_address).order('created_at', desc=True).limit(1).execute()
        if last_order.data:
            last_ts_str = last_order.data[0]['created_at']
            # Parse ISO (handle Z if present)
            last_ts = datetime.fromisoformat(last_ts_str.replace('Z', '+00:00'))
            if (datetime.now(timezone.utc) - last_ts).total_seconds() < 60:
                 return jsonify({"error": "Rate limit exceeded. Please wait 1 minute."}), 429
    except Exception as e:
        print(f"Rate limit check fail: {e}")
        # Fail open (allow order) if rate limit check fails

    try:
        # Calculate final price again to prevent tampering
        price_info = calculate_total(
            pages=data.get('pages', 1),
            copies=data.get('copies', 1),
            color=data.get('color', 'BW'),
            sides=data.get('sides', 'SINGLE')
        )
        
        order_data = {
            "customer_name": data.get('customer_name'),
            "customer_phone": data.get('customer_phone'),
            "file_name": data.get('file_name'),
            "file_url": data.get('file_url'),
            "file_type": data.get('file_type'),
            "pages": data.get('pages'),
            "copies": data.get('copies'),
            "total_sheets": price_info['total_sheets'],
            "print_color": data.get('color'),
            "print_sides": data.get('sides'),
            "orientation": data.get('orientation'),
            "total_amount": price_info['price'],
            "payment_method": data.get('payment_method'),
            "payment_status": "PENDING_VERIFICATION" if data.get('payment_method') == 'UPI' else "PENDING",
            "order_status": "PENDING",
            # Consent Data
            "accepted_terms": True,
            "accepted_at": accepted_at,
            "ip_address": ip_address,
            "user_agent": user_agent
        }
        
        res = supabase.client.table('orders').insert(order_data).execute()
        
        if res.data:
            notify_shop(order_data)
            return jsonify({"status": "success", "order": res.data[0]})
        else:
            return jsonify({"error": "Failed to create order"}), 500
            
    except Exception as e:
        print(f"Create order error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/cron/cleanup')
def cron_cleanup():
    # Security: Require CRON_SECRET
    secret = os.environ.get('CRON_SECRET')
    if not secret:
        # Fail secure if not configured
        return jsonify({"error": "Cron secret not configured on server"}), 500
        
    auth_header = request.headers.get('Authorization')
    if auth_header != f"Bearer {secret}":
         return jsonify({"error": "Unauthorized"}), 401

    # Cleanup files for orders older than 24 hours
    try:
        supabase = get_supabase_client()
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        
        # Find orders with files created > 24h ago
        res = supabase.client.table('orders').select('id, file_url').lt('created_at', cutoff).execute()
        
        count = 0
        deleted_log = []
        for order in (res.data or []):
            if order.get('file_url'):
                # Delete
                f_url = order['file_url']
                try:
                    if '/uploads/' in f_url:
                        path = unquote(f_url.split('/uploads/')[-1])
                        supabase.client.storage.from_("uploads").remove([path])
                        deleted_log.append(path)
                except: pass
                
                # Update DB
                supabase.client.table('orders').update({"file_url": None}).eq("id", order['id']).execute()
                count += 1
                
        return jsonify({"success": True, "deleted_count": count, "files": deleted_log})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/shop/orders', methods=['GET'])
@login_required
def get_shop_orders():
    try:
        supabase = get_supabase_client()
        # Fetch ACTIVE orders only (exclude COMPLETED)
        res = supabase.client.table('orders').select("*")\
            .neq('order_status', 'COMPLETED')\
            .order('created_at', desc=True).limit(50).execute()
        return jsonify(res.data)
    except Exception as e:
        print(f"Fetch orders error: {e}")
        return jsonify([]), 500

def log_admin_action(action_type, order_id=None):
    try:
        supabase = get_supabase_client()
        ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        supabase.client.table('admin_logs').insert({
            "action_type": action_type,
            "order_id": order_id,
            "admin_ip": ip,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }).execute()
    except Exception as e:
        print(f"[LOG ERROR] Failed to log {action_type}: {e}")

@app.route('/api/shop/orders/<order_id>/status', methods=['POST'])
@login_required
def update_order_status(order_id):
    data = request.json
    new_status = data.get('status')
    
    try:
        supabase = get_supabase_client()
        res = supabase.client.table('orders').update({"order_status": new_status}).eq("id", order_id).execute()
        if not res.data:
            return jsonify({"error": "Update failed. Database Permissions (RLS) blocked the change."}), 500
        
        # Audit Log
        log_admin_action(f"UPDATE_STATUS_{new_status}", order_id)

        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/shop/orders/<order_id>/payment', methods=['POST'])
@login_required
def update_payment_status(order_id):
    data = request.json
    new_status = data.get('status') # e.g., 'PAID'
    
    try:
        supabase = get_supabase_client()
        res = supabase.client.table('orders').update({"payment_status": new_status}).eq("id", order_id).execute()
        if not res.data:
            return jsonify({"error": "Payment Update failed. Database Permissions (RLS) blocked the change."}), 500
        
        # Audit Log
        log_admin_action(f"UPDATE_PAYMENT_{new_status}", order_id)

        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/shop/qr-verify', methods=['POST'])
@login_required
def verify_qr_order():
    data = request.json
    order_id = data.get('order_id')
    
    try:
        supabase = get_supabase_client()
        # 1. Fetch Order
        res = supabase.client.table('orders').select("*").eq('id', order_id).execute()
        if not res.data:
            return jsonify({"error": "Order not found"}), 404
        
        order = res.data[0]
        
        # 2. Mark as COMPLETED and Payment PAID
        supabase.client.table('orders').update({
            "order_status": "COMPLETED",
            "payment_status": "PAID"
        }).eq("id", order_id).execute()
        
        # Audit Log
        log_admin_action("QR_VERIFY_COMPLETE", order_id)
        
        # 3. Secure Deletion (File Lifecycle Policy)
        # Delete file immediately upon completion
        file_url = order.get('file_url')
        if file_url:
            print(f"[SECURE] Deleting file for order {order_id}")
            try:
                if '/uploads/' in file_url:
                    path = unquote(file_url.split('/uploads/')[-1])
                    supabase.client.storage.from_("uploads").remove([path])
            except Exception as e:
                print(f"[DELETE ERROR] {e}")
                
            # Remove link from DB
            supabase.client.table('orders').update({
                "file_url": None
            }).eq("id", order_id).execute()
        
        return jsonify({
            "success": True, 
            "message": "Order verified and completed. File securely deleted."
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

def find_upload_path(filename):
    decoded_name = unquote(filename)
    # Check phase-2 uploads
    p2_path = os.path.join(app.root_path, '../uploads', decoded_name)
    if os.path.exists(p2_path):
        return p2_path
    return None

@app.route('/api/shop/order-file/<order_id>', methods=['GET'])
@login_required
def serve_order_file(order_id):
    try:
        supabase = get_supabase_client()
        res = supabase.client.table('orders').select("*").eq('id', order_id).execute()
        if not res.data:
            return jsonify({"error": "Order not found"}), 404

        order = res.data[0]
        file_url = order.get('file_url', '')
        if not file_url:
            return jsonify({"error": "No file url in order"}), 404

        raw_name = file_url.split('/')[-1].split('?')[0]
        filename = unquote(raw_name)
        file_path = find_upload_path(filename)

        # 1. Local file (Range-enabled)
        if file_path and os.path.exists(file_path):
            log_admin_action("FILE_DOWNLOAD", order_id)
            return send_file(
                file_path,
                mimetype='application/pdf',
                as_attachment=False,
                conditional=True
            )

        # 2. Supabase Proxy (Enforce Correct MIME Type)
        if file_url.startswith('http'):
            log_admin_action("FILE_DOWNLOAD", order_id)
            
            try:
                # Extract path
                path = unquote(file_url.split('/')[-1].split('?')[0])
                
                # Fetch file bytes from Supabase storage
                # This ensures we control the serving headers, preventing 'text/plain' issue
                file_bytes = supabase.client.storage.from_("uploads").download(path)
                
                # Determine MIME type
                mimetype = 'application/pdf'
                if path.lower().endswith(('.jpg', '.jpeg')):
                    mimetype = 'image/jpeg'
                elif path.lower().endswith('.png'):
                    mimetype = 'image/png'
                
                from io import BytesIO
                return send_file(
                    BytesIO(file_bytes),
                    mimetype=mimetype,
                    as_attachment=False, # Open in browser
                    download_name=path.replace(path.split('_')[0] + '_', '') # Clean filename
                )
                    
            except Exception as e:
                print(f"Proxy download failed: {e}")
                # Fallback to redirect if proxy fails
                return redirect(file_url)

        return jsonify({"error": "Unable to serve file"}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/config')
def get_config():
    return jsonify({
        "shop_name": os.environ.get("SHOP_NAME", "Barath Store"),
        "upi_id": os.environ.get("UPI_ID", "kalpanav856-1@oksbi")
    })

@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if file:
        filename = secure_filename(file.filename)
        try:
            supabase = get_supabase_client()
            file_content = file.read()
            unique_name = f"{uuid.uuid4()}_{filename}"
            
            res = supabase.client.storage.from_("uploads").upload(
                path=unique_name,
                file=file_content,
                file_options={"content-type": file.content_type}
            )
            
            public_url = supabase.client.storage.from_("uploads").get_public_url(unique_name)
            
            pages = 1 
            if filename.lower().endswith('.pdf'):
                try:
                    import pypdf
                    from io import BytesIO
                    pdf_file = pypdf.PdfReader(BytesIO(file_content))
                    pages = len(pdf_file.pages)
                except:
                    print("Could not count PDF pages, defaulting to 1")

            return jsonify({
                "message": "File uploaded successfully",
                "url": public_url,
                "filename": unique_name, 
                "pages": pages,
                "type": "PDF" if filename.lower().endswith('.pdf') else "IMAGE"
            })
            
        except Exception as e:
            return jsonify({"error": str(e)}), 500

@app.route('/api/calculate-price', methods=['POST'])
def calculate_price_endpoint():
    try:
        data = request.json
        res = calculate_total(
            pages=data.get('pages', 1),
            copies=data.get('copies', 1),
            color=data.get('color', 'BW'),
            sides=data.get('sides', 'SINGLE')
        )
        return jsonify(res)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/health')
def health_check():
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "site_type": os.environ.get("SITE_TYPE", "UNSET")
    })

if __name__ == '__main__':
    app.run(debug=True, port=5001)
