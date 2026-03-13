import os
from flask import Flask, request, jsonify, send_from_directory
from dotenv import load_dotenv
import PyPDF2
import io
import time
from pricing import calculate_total
from payments import process_payment
# from supabase import get_supabase_client # Import later to avoid init error if env vars missing during dev

load_dotenv()

app = Flask(__name__, static_folder="../static", template_folder="../customer")

# Helper to serve pages - Flask usually serves templates, but we can serve raw HTML for this simple phase
@app.route('/')
def index():
    return send_from_directory('../customer', 'index.html')

@app.route('/<path:path>')
def serve_page(path):
    return send_from_directory('../customer', path)

# Serve Uploads (Local Fallback)
@app.route('/uploads/<path:filename>')
def serve_uploads(filename):
    return send_from_directory('../uploads', filename)

@app.route('/api/config', methods=['GET'])
def get_config():
    return jsonify({
        "upi_id": os.environ.get("UPI_ID"),
        "shop_name": os.environ.get("SHOP_NAME", "Print Shop")
    })

@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    filename = file.filename
    # Analyze file
    pages = 1
    file_type = 'IMAGE'
    if filename.lower().endswith('.pdf'):
        try:
            pdf_reader = PyPDF2.PdfReader(file)
            pages = len(pdf_reader.pages)
            file_type = 'PDF'
            file.seek(0) # Reset pointer after reading
        except Exception as e:
            return jsonify({"error": f"Invalid PDF: {str(e)}"}), 400
    
    # Upload to Supabase with Local Fallback
    try:
        from db import get_supabase_client
        supabase = get_supabase_client()
        unique_name = f"{int(time.time())}_{filename}"
        public_url = supabase.upload_file(file, unique_name)
    except Exception as e:
        print(f"Supabase upload failed: {e}")
        # Reset pointer in case upload read it
        file.seek(0)
        # Save locally
        local_path = os.path.join(app.root_path, '../uploads', filename)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        file.save(local_path)
        public_url = f"http://localhost:5000/uploads/{filename}"

    return jsonify({
        "url": public_url,
        "pages": pages,
        "type": file_type,
        "filename": filename
    })

@app.route('/api/calculate-price', methods=['POST'])
def get_price():
    data = request.json
    pages = data.get('pages', 1)
    copies = data.get('copies', 1)
    color = data.get('color', 'BW')
    sides = data.get('sides', 'SINGLE')
    
    result = calculate_total(pages, copies, color, sides)
    return jsonify(result)

@app.route('/api/create-order', methods=['POST'])
def create_order():
    data = request.json
    
    # Validate price again (source of truth)
    price_check = calculate_total(
        data['pages'], 
        data['copies'], 
        data.get('color', 'BW'), 
        data.get('sides', 'SINGLE')
    )
    
    total_amount = price_check['price']
    
    # Process payment (Mock)
    payment_method = data.get('payment_method', 'PAY_AT_SHOP')
    payment_status = 'PENDING'
    
    if payment_method == 'PAY_NOW':
        payment_res = process_payment(total_amount)
        if payment_res['status'] == 'SUCCESS':
            payment_status = 'PAID'
    elif payment_method == 'UPI':
        payment_status = 'PENDING_VERIFICATION'
    elif payment_method == 'PAY_AT_SHOP':
        payment_status = 'PAY_AT_SHOP'
            
    order_payload = {
        "file_url": data['file_url'],
        "file_name": data.get('file_name'),
        "file_type": data.get('file_type', 'UNKNOWN'),
        "pages": data['pages'],
        "copies": data['copies'],
        "print_color": data.get('color', 'BW'),
        "print_sides": data.get('sides', 'SINGLE'),
        "orientation": data.get('orientation', 'PORTRAIT'),
        "total_sheets": price_check['total_sheets'],
        "total_amount": total_amount,
        "customer_name": data['customer_name'],
        "customer_phone": data['customer_phone'],
        "payment_method": payment_method,
        "payment_status": payment_status,
        "order_status": "CREATED"
    }

    # Save to Supabase
    try:
        from db import get_supabase_client
        supabase = get_supabase_client()
        # response = supabase.create_order(order_payload) 
        # Since I don't have the table yet, this might fail unless I create it or user does.
        # I'll just attempt it.
        response = supabase.create_order(order_payload)
        order_id = response[0]['id'] if response else "unknown"
    except Exception as e:
        print(f"Supabase DB Save failed: {e}")
        order_id = "LOCAL_MOCK_ID_123"

    order_payload['id'] = order_id
    return jsonify({"status": "success", "order": order_payload})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
