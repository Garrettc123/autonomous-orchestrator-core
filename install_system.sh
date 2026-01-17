#!/data/data/com.termux/files/usr/bin/bash
set -e

# --- CONFIGURATION ---
PREFIX="/data/data/com.termux/files/usr"
LOG_FILE="$HOME/system_prime.log"

echo ">>> SYSTEM PRIME: FORCE DEPLOYMENT..."

# 1. SETUP HOST TOOLS (Fast)
echo ">>> [1/5] Host Tools OK."
pkg install git wget proot-distro nginx nodejs-lts python build-essential -y > /dev/null 2>&1

# 2. SETUP UBUNTU ENGINE (Force Config)
echo ">>> [2/5] Configuring Backend Engine..."
# We SKIP the install command because we know it exists.
# We go straight to creating the internal setup script.

cat << 'EOF' > ~/setup_internal.sh
#!/bin/bash
export DEBIAN_FRONTEND=noninteractive
echo ">>> [UBUNTU] Installing Dependencies..."

# Dependencies
apt update -y
apt install -y git python3-pip build-essential wget python3-dev python3-venv \
    python3-wheel libxslt-dev libzip-dev libldap2-dev libsasl2-dev \
    libjpeg-dev zlib1g-dev libpq-dev postgresql

# Database
service postgresql start
if ! su - postgres -c "psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='odoo'"" | grep -q 1; then
    su - postgres -c "createuser -s odoo"
fi

# User & Source
useradd -m -d /opt/odoo -U -r -s /bin/bash odoo || true
mkdir -p /opt/odoo
if [ ! -d "/opt/odoo/server" ]; then
    git clone https://github.com/odoo/odoo.git --depth 1 --branch 17.0 /opt/odoo/server
fi

# Python Environment
cd /opt/odoo/server
if [ ! -d "venv" ]; then
    echo ">>> [UBUNTU] Creating Virtual Environment (This takes time)..."
    python3 -m venv venv
    source venv/bin/activate
    pip3 install wheel
    pip3 install -r requirements.txt
else
    echo ">>> [UBUNTU] Venv exists. Skipping pip install."
fi
EOF

# Execute Internal Setup
echo ">>> [2/5] Running Internal Setup..."
proot-distro login ubuntu --shared-tmp -- bash -c "bash /data/data/com.termux/files/home/setup_internal.sh"

# 3. SETUP FRONTEND (Safe Re-run)
echo ">>> [3/5] Verifying Frontend..."
mkdir -p ~/system-prime
cd ~/system-prime

if [ ! -d "frontend" ]; then
    echo ">>> Creating React App..."
    npm create vite@latest frontend -- --template react-ts
    cd frontend
    npm install
    npm install -D tailwindcss postcss autoprefixer
    npx tailwindcss init -p
    
    # Configure Tailwind
    cat << 'INNER' > tailwind.config.js
export default { content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"], theme: { extend: {} }, plugins: [] }
INNER
    echo "@tailwind base; @tailwind components; @tailwind utilities;" > src/index.css

    # Dashboard Code
    mkdir -p src/lib
    cat << 'INNER' > src/lib/odoo-client.ts
export class OdooClient {
  async jsonRpc(route: string, params: any) {
    const res = await fetch(route, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ jsonrpc: '2.0', method: 'call', params: params, id: 1 })
    });
    return res.json();
  }
  async authenticate(l: string, p: string, d: string = 'postgres') { return this.jsonRpc('/web/session/authenticate', { db: d, login: l, password: p }); }
  async getEvents() { return this.jsonRpc('/web/dataset/call_kw', { model: 'event.event', method: 'search_read', args: [[], ['name', 'date_begin', 'state']], kwargs: { limit: 10 } }); }
}
export const client = new OdooClient();
INNER

    cat << 'INNER' > src/App.tsx
import { useEffect, useState } from 'react';
import { client } from './lib/odoo-client';
export default function App() {
  const [s, setS] = useState(false);
  const [e, setE] = useState<any[]>([]);
  useEffect(() => { 
      client.authenticate("admin","admin").then(r => { 
          if(r.result) { setS(true); client.getEvents().then(ev => setE(ev.result || [])); } 
      }).catch(()=>console.log("Connecting...")); 
  }, []);
  return (
    <div className="min-h-screen bg-slate-950 text-white p-8 font-sans">
      <h1 className="text-3xl font-bold text-emerald-500 mb-6 tracking-tighter">SYSTEM PRIME // COMMANDER</h1>
      {!s && <div className="p-4 bg-slate-900 border border-slate-700 rounded animate-pulse">Establishing Neural Link...</div>}
      {e.map((ev:any) => (
          <div key={ev.id} className="p-4 mb-2 bg-slate-900 border border-slate-800 rounded hover:border-emerald-500">
            <h3 className="font-bold text-lg">{ev.name}</h3>
            <p className="text-sm text-slate-400">{ev.date_begin}</p>
          </div>
      ))}
    </div>
  );
}
INNER

    # Fix TSConfig
    sed -i 's|"paths": {|"baseUrl": ".", "paths": { "@/*": ["src/*"],|' tsconfig.json
else
    echo ">>> Frontend directory exists. Skipping creation."
    cd frontend
fi

echo ">>> Compiling Assets..."
npm run build

# 4. SETUP GATEWAY (Safe Re-run)
echo ">>> [4/5] Configuring Gateway..."
mkdir -p ~/.config/nginx
cp "$PREFIX/etc/nginx/mime.types" ~/.config/nginx/ 2>/dev/null || true

cat <<EOF > ~/.config/nginx/nginx.conf
worker_processes 1;
events { worker_connections 1024; }
http {
    include mime.types;
    default_type application/octet-stream;
    sendfile on;
    upstream odoo { server 127.0.0.1:8069; }
    server {
        listen 8080;
        server_name localhost;
        location / {
            root /data/data/com.termux/files/home/system-prime/frontend/dist;
            index index.html;
            try_files $uri $uri/ /index.html;
        }
        location /web { proxy_pass http://odoo; proxy_set_header Host $host; proxy_set_header X-Real-IP $remote_addr; }
        location /jsonrpc { proxy_pass http://odoo; proxy_set_header Host $host; }
    }
}
EOF

# 5. LAUNCH
echo ">>> [5/5] Launching Systems..."
pkill nginx 2>/dev/null || true
nginx -c ~/.config/nginx/nginx.conf

echo ">>> Booting Odoo Engine (Background)..."
proot-distro login ubuntu --shared-tmp -- bash -c "
    pkill -f odoo-bin
    service postgresql start
    su - odoo -c 'cd /opt/odoo/server && source venv/bin/activate && nohup ./odoo-bin --http-port=8069 --without-demo=all > /dev/null 2>&1 &'
"

echo ">>> DEPLOYMENT SUCCESSFUL."
echo ">>> Access Dashboard: http://localhost:8080"
termux-open-url http://localhost:8080
