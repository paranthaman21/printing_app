# 🖨️ Online Print Pickup System - Project Documentation

## 📋 Table of Contents
1. [Project Overview](#project-overview)
2. [Local Development Guide](#local-development-guide)
3. [Deployment Guide (Vercel)](#deployment-guide-vercel)
4. [Environment Configuration](#environment-configuration)
5. [Security & Cron Jobs](#security--cron-jobs)
6. [System Architecture](#system-architecture)
7. [API Endpoints](#api-endpoints)
8. [Database Schema](#database-schema)

---

## 🎯 Project Overview

**Barath Store - Online Print Pickup System** is a production-ready, serverless web application. It allows customers to upload documents, configure print settings, and pay online. Shopkeepers receive orders in real-time, print them, and verify pickup via QR code.

**Key Components:**
*   **Customer Portal**: Mobile-friendly upload & checkout.
*   **Shopkeeper Dashboard**: Admin panel for order management & QR scanning.
*   **Backend API**: Flask + Supabase (PostgreSQL & Storage).

---

## 💻 Local Development Guide

Follow these steps to run the project on your local machine.

### Prerequisites
*   **Python 3.12+**
*   **pip** (Python package manager)
*   **Git**

### Step-by-Step Setup

1.  **Clone the Repository**
    ```bash
    git clone <your-repo-url>
    cd <your-repo-folder>
    ```

2.  **Navigate to the Project Root**
    This project is located in the `phase-2` directory.
    ```bash
    cd phase-2
    ```

3.  **Install Dependencies**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure Environment Variables**
    Create a `.env` file in the `phase-2` folder:
    ```bash
    # duplicate the example
    copy .env.example .env
    ```
    *Edit `.env` and add your credentials (see [Environment Configuration](#environment-configuration)).*

5.  **Run the Application**
    ```bash
    python backend/app.py
    ```
    The server will start at `http://127.0.0.1:5001`.

6.  **Access the App**
    *   **Customer Portal**: [http://127.0.0.1:5001](http://127.0.0.1:5001)
    *   **Shopkeeper Dashboard**: [http://127.0.0.1:5001/admin](http://127.0.0.1:5001/admin)

---

## 🚀 Deployment Guide (Vercel)

This project is designed to be deployed on **Vercel** as a serverless Python application. Since the project lives in the `phase-2` subdirectory, you must configure the **Root Directory** settings.

### Method 1: Vercel Dashboard (Recommended)

1.  **Push to GitHub**: Ensure your code is pushed to a GitHub repository.
2.  **Import Project**: Go to Vercel Dashboard > **Add New...** > **Project** > Import your repository.
3.  **Configure Project Root (CRITICAL)**:
    *   In the "Configure Project" screen, look for **Root Directory**.
    *   Click **Edit**.
    *   Select `phase-2` folder.
    *   *Why? This tells Vercel that `vercel.json` and `requirements.txt` are inside `phase-2`, not the top level.*
4.  **Environment Variables**:
    *   Expand **Environment Variables**.
    *   Add all variables listed in the [Environment Configuration](#environment-configuration) section.
5.  **Deploy**: Click **Deploy**.

### Method 2: Vercel CLI

If you prefer using the command line:

1.  Navigate to the `phase-2` directory:
    ```bash
    cd phase-2
    ```
2.  Run Vercel deploy:
    ```bash
    vercel
    ```
3.  Follow the prompts. When asked `? Link to existing project?`, select No (or Yes if updating).
4.  **Important**: If Vercel asks about the root directory, confirm you are deploying the current directory (`phase-2`).

---

## ⚙️ Environment Configuration

You must set these environment variables in your local `.env` file and in the Vercel Project Settings.

| Variable | Description | Example Value |
| :--- | :--- | :--- |
| `SUPABASE_URL` | Your Supabase Project URL | `https://xyz.supabase.co` |
| `SUPABASE_KEY` | **Service Role Key** (Required for Admin access) | `eyJhbG...` (Note: Do NOT use the Anon key) |
| `ADMIN_PASS` | Password for Shopkeeper Login | `MySecurePassword123!` |
| `SECRET_KEY` | Flask Session Secret (Random String) | `9a9ebf8...` (Generate using python secrets) |
| `SHOP_NAME` | Display Name of the Shop | `Barath Store` |
| `CRON_SECRET` | Secret for securing Cron Jobs | `my-cron-secret-value` |
| `UPI_ID` | UPI ID for Payments | `merchant@upi` |

**Generating a Secret Key:**
Run this command in your terminal:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## 🛡️ Security & Cron Jobs

### 1. Cron Job (Auto-Cleanup)
The system includes a daily cron job to delete old files (privacy compliance).
*   **Path**: `/api/cron/cleanup`
*   **Schedule**: UTC 00:00 (Daily)
*   **Security**: Protected by `CRON_SECRET`.

**To Enable on Vercel:**
1.  Go to Vercel Project Settings > **Environment Variables**.
2.  Add `CRON_SECRET` with a strong random value.
3.  Vercel Cron automatically uses this secret to authenticate the job.

### 2. Admin Security
*   **POST-Only Logout**: Prevents CSRF attacks.
*   **Rate Limiting**: Limits order creation (1 per minute per IP).
*   **Audit Logs**: Tracks all admin actions (Status changes, Downloads) in the `admin_logs` table.

---

## 🏗️ System Architecture

*   **Frontend**: Pure HTML/JS (No framework). Served dynamically by Flask.
    *   `customer/`: Public facing pages.
    *   `shopkeeper/`: Protected admin pages.
*   **Backend**: Python Flask (Serverless function on Vercel).
    *   `app.py`: Main logic.
    *   `pricing.py`: Price calculation logic.
*   **Database**: Supabase (PostgreSQL).
*   **File Storage**: Supabase Storage (`uploads` bucket).

## 🔌 API Endpoints

### Customer
*   `POST /api/upload`: Upload file (Returns URL).
*   `POST /api/create-order`: Submit order (Requires `accepted_terms`).
*   `POST /api/calculate-price`: Get price estimate.

### Shopkeeper (Protected)
*   `GET /api/shop/orders`: List active orders.
*   `POST /api/shop/orders/<id>/status`: Update status (e.g., COMPLETED).
*   `POST /api/shop/qr-verify`: Verify pickup via QR.
*   `GET /api/shop/order-file/<id>`: Secure file download.

## 🗄️ Database Schema

### Table: `orders`
| Column | Type | Notes |
| :--- | :--- | :--- |
| `id` | UUID | Primary Key |
| `order_status` | TEXT | PENDING, COMPLETED |
| `payment_status` | TEXT | PENDING, PENDING_VERIFICATION, PAID |
| `file_url` | TEXT | Link to Supabase Storage (Nullable after cleanup) |
| `accepted_terms` | BOOLEAN | **Required** for GDPR/Privacy |
| `ip_address` | TEXT | Audit Trail |

### Table: `admin_logs`
| Column | Type | Notes |
| :--- | :--- | :--- |
| `action_type` | TEXT | e.g., FILE_DOWNLOAD, QR_VERIFY |
| `admin_ip` | TEXT | IP of the admin |
| `timestamp` | TIMESTAMPTZ | Time of action |
