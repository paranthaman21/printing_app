-- Create the orders table
create table public.orders (
  id uuid default gen_random_uuid() primary key,
  created_at timestamp with time zone default now() not null,
  
  -- Customer Details
  customer_name text not null,
  customer_phone text not null,
  
  -- File Details
  file_url text not null,
  file_name text,
  file_type text, -- 'PDF' or 'IMAGE'
  
  -- Order Specs
  pages integer not null default 1,
  copies integer not null default 1,
  print_color text not null default 'BW', -- 'BW' or 'COLOR'
  print_sides text not null default 'SINGLE', -- 'SINGLE' or 'DOUBLE'
  orientation text default 'PORTRAIT', -- 'PORTRAIT' or 'LANDSCAPE'
  
  -- Calculations
  total_sheets integer not null default 1,
  total_amount numeric not null default 0.00,
  
  -- Payment & Status
  payment_method text not null, -- 'PAY_NOW', 'PAY_AT_SHOP'
  payment_status text not null default 'PENDING', -- 'PAID', 'PENDING'
  order_status text not null default 'CREATED' -- 'CREATED', 'COMPLETED', etc.
);

-- Turn on Row Level Security (Recommended for production, though optional for pure backend access via service key)
alter table public.orders enable row level security;

-- Create a policy to allow public inserts (if customers insert directly) 
-- OR strictly rely on the backend via Service Key. 
-- Since we are using python backend with what is likely a service_role key or authenticated client, 
-- we can set policies or just leave RLS on. 
-- For Phase 1 simplified backend usage:
create policy "Enable insert for authenticated users and service role"
on public.orders for insert
with check (true);

create policy "Enable read access for all"
on public.orders for select
using (true);
