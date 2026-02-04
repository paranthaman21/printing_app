import os
import shutil
import uuid
from flask import Flask, request, jsonify, send_from_directory, session, redirect, send_file
from dotenv import load_dotenv
import time
from db import get_supabase_client

# Load .env from parent directory (phase-2/.env)
env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(env_path)

app = Flask(__name__, static_folder="../static", template_folder="../shopkeeper")

# Secret key for sessions
app.secret_key = os.environ.get("SECRET_KEY", "super_secret_shopkeeper_key")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASS", "admin123")
TEMP_SECURE_DIR = os.path.join(app.root_path, '../secure_temp')
os.makedirs(TEMP_SECURE_DIR, exist_ok=True)

# Security configurations
IS_PRODUCTION = os.environ.get('VERCEL_ENV') == 'production'
app.config['SESSION_COOKIE_SECURE'] = IS_PRODUCTION  # HTTPS only in production
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1 hour

# Add security headers to all responses
@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    # Allow same-origin for dashboard functionality
    if 'Access-Control-Allow-Origin' not in response.headers:
        response.headers['Access-Control-Allow-Origin'] = 'http://127.0.0.1:5001'
    return response

# Helper: Store tokens
download_tokens = {}

# --- Shopkeeper Routes ---

@app.route('/')
def index():
    return redirect('/admin')

@app.route('/admin')
def admin_dashboard():
    if not session.get('logged_in'):
        return send_from_directory('../shopkeeper', 'login.html')
    return send_from_directory('../shopkeeper', 'dashboard.html')

@app.route('/admin/login', methods=['POST'])
def admin_login():
    data = request.json
    if data.get('password') == ADMIN_PASSWORD:
        session['logged_in'] = True
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Invalid Password"}), 401

@app.route('/admin/logout')
def admin_logout():
    session.pop('logged_in', None)
    return jsonify({"success": True})

# Serve Shopkeeper Pages
@app.route('/shopkeeper/<path:path>')
def serve_shop_pages(path):
    if not session.get('logged_in') and 'login.html' not in path:
        return redirect('/admin')
    return send_from_directory('../shopkeeper', path)

# Serve Shared Static Assets (CSS/JS) if needed, or specific shop assets
# Phase 2 has its own static folder now, so we serve from there
@app.route('/static/<path:path>')
def serve_static(path):
    return send_from_directory('../static', path)


# --- API Endpoints (Shopkeeper Only) ---

from datetime import datetime, timedelta, timezone

# ... imports ...

@app.route('/api/shop/stats', methods=['GET'])
def get_shop_stats():
    if not session.get('logged_in'):
        return jsonify({"error": "Unauthorized"}), 401
        
    try:
        supabase = get_supabase_client()
        
        # 1. Pending Prints (Active orders)
        res_pending = supabase.client.table('orders').select('id', count='exact').neq('order_status', 'COMPLETED').execute()
        count_pending = res_pending.count if res_pending.count is not None else len(res_pending.data)
        
        # 2. UPI Verification
        res_verify = supabase.client.table('orders').select('id', count='exact').eq('payment_status', 'PENDING_VERIFICATION').execute()
        count_verify = res_verify.count if res_verify.count is not None else len(res_verify.data)
        
        # 3. Today's Revenue (IST)
        # IST is UTC+5:30
        ist_offset = timezone(timedelta(hours=5, minutes=30))
        now_ist = datetime.now(ist_offset)
        start_of_day_ist = now_ist.replace(hour=0, minute=0, second=0, microsecond=0)
        # Convert to UTC for database query
        start_of_day_utc = start_of_day_ist.astimezone(timezone.utc)
        
        print(f"[REVENUE DEBUG] Current IST: {now_ist}")
        print(f"[REVENUE DEBUG] Start of day UTC: {start_of_day_utc.isoformat()}")
        
        res_revenue = supabase.client.table('orders')\
            .select('total_amount, payment_status, created_at')\
            .eq('payment_status', 'PAID')\
            .gte('created_at', start_of_day_utc.isoformat())\
            .execute()
        
        print(f"[REVENUE DEBUG] Found {len(res_revenue.data or [])} PAID orders")
        print(f"[REVENUE DEBUG] Revenue data: {res_revenue.data}")
            
        revenue = sum((item.get('total_amount') or 0) for item in (res_revenue.data or []))
        print(f"[REVENUE DEBUG] Total revenue: {revenue}")
        
        return jsonify({
            "pending_print": count_pending,
            "upi_verify": count_verify,
            "revenue_today": revenue
        })
        
    except Exception as e:
        print(f"Stats error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/shop/orders', methods=['GET'])
def get_shop_orders():
    if not session.get('logged_in'):
        return jsonify({"error": "Unauthorized"}), 401
        
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

@app.route('/api/shop/orders/<order_id>/status', methods=['POST'])
def update_order_status(order_id):
    if not session.get('logged_in'): return jsonify({"error": "Unauthorized"}), 401
    
    data = request.json
    new_status = data.get('status')
    
    try:
        supabase = get_supabase_client()
        print(f"[DEBUG] Attempting to update order {order_id} to status: {new_status}")
        res = supabase.client.table('orders').update({"order_status": new_status}).eq("id", order_id).execute()
        print(f"[DEBUG] Response data: {res.data}")
        print(f"[DEBUG] Response count: {len(res.data) if res.data else 0}")
        if not res.data:
            print(f"Update failed for {order_id}: RLS/Permissions or ID not found")
            return jsonify({"error": "Update failed. Database Permissions (RLS) blocked the change."}), 500
        return jsonify({"success": True})
    except Exception as e:
        print(f"[ERROR] Exception during update: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/shop/orders/<order_id>/payment', methods=['POST'])
def update_payment_status(order_id):
    if not session.get('logged_in'): return jsonify({"error": "Unauthorized"}), 401
    
    data = request.json
    new_status = data.get('status') # e.g., 'PAID'
    
    try:
        supabase = get_supabase_client()
        res = supabase.client.table('orders').update({"payment_status": new_status}).eq("id", order_id).execute()
        if not res.data:
            print(f"Payment update failed for {order_id}: RLS/Permissions")
            return jsonify({"error": "Payment Update failed. Database Permissions (RLS) blocked the change."}), 500
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- SECURE QR & FILE HANDLING ---

from urllib.parse import unquote

# ... imports ...

@app.route('/api/shop/qr-verify', methods=['POST'])
def verify_qr_order():
    if not session.get('logged_in'): return jsonify({"error": "Unauthorized"}), 401
    
    data = request.json
    order_id = data.get('order_id')
    
    try:
        supabase = get_supabase_client()
        # 1. Fetch Order to confirm it exists
        res = supabase.client.table('orders').select("*").eq('id', order_id).execute()
        if not res.data:
            return jsonify({"error": "Order not found"}), 404
        
        order = res.data[0]
        
        # 2. Mark as COMPLETED (Verify & "Delete" from dashboard view)
        supabase.client.table('orders').update({
            "order_status": "COMPLETED",
            "payment_status": "PAID" # Ensure it's marked paid if they are picking up
        }).eq("id", order_id).execute()
        
        return jsonify({
            "success": True, 
            "message": "Order verified and completed successfully."
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

def find_upload_path(filename):
    # Decode URL-encoded filename (e.g. "My%20File.pdf" -> "My File.pdf")
    decoded_name = unquote(filename)
    
    # Check phase-2 uploads
    p2_path = os.path.join(app.root_path, '../uploads', decoded_name)
    if os.path.exists(p2_path):
        return p2_path
    
    # Check phase-1 uploads (fallback)
    p1_path = os.path.abspath(os.path.join(app.root_path, '../../phase-1/uploads', decoded_name))
    if os.path.exists(p1_path):
        return p1_path
        
    return None

@app.route('/api/shop/order-file/<order_id>', methods=['GET'])
def serve_order_file(order_id):
    if not session.get('logged_in'): return jsonify({"error": "Unauthorized"}), 401
    
    try:
        supabase = get_supabase_client()
        res = supabase.client.table('orders').select("*").eq('id', order_id).execute()
        if not res.data:
            return jsonify({"error": "Order not found"}), 404
            
        order = res.data[0]
        file_url = order.get('file_url', '')
        if not file_url:
             return jsonify({"error": "No file url in order"}), 404
             
        # Extract filename from URL (handle cases like http://localhost:5000/uploads/My%20File.pdf)
        # 1. Get last part
        raw_name = file_url.split('/')[-1]
        # 2. Remove queries
        raw_name = raw_name.split('?')[0]
        # 3. Decode
        filename = unquote(raw_name)
        
        file_path = find_upload_path(filename)
        
        # 1. Try Local File
        if file_path and os.path.exists(file_path):
            # Check for size 0 (corrupted upload)
            if os.path.getsize(file_path) > 0:
                print(f"Serving local file: {file_path}")
                mime = 'application/pdf' if filename.lower().endswith('.pdf') else None
                return send_file(file_path, mimetype=mime)
            else:
                print(f"Local file found but empty: {file_path}")
                
        # 2. Fallback: Redirect to the URL (Supabase or Phase 1 Server)
        # If local file is missing or empty, maybe the URL points to a valid cloud resource 
        # or the other server can handle it.
        if file_url.startswith('http'):
            print(f"Redirecting to source URL: {file_url}")
            return redirect(file_url)
            
        return jsonify({"error": f"File '{filename}' not found locally and no valid URL to redirect."}), 404
        
    except Exception as e:
        print(f"Serve error: {e}")
        return jsonify({"error": str(e)}), 500
        


if __name__ == '__main__':
    app.run(debug=True, port=5001)
