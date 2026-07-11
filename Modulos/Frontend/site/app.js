const state = {
  route: "login",
  session: JSON.parse(localStorage.getItem("cloudshop-session") || "null"),
  cart: JSON.parse(localStorage.getItem("cloudshop-cart") || "[]"),
};

const config = window.CLOUDSHOP_CONFIG || { apis: {} };
const app = document.querySelector("#app");
const demoData = {
  sales: { totalSales: 1250.75, orderCount: 18 },
  stores: [{ storeId: "store-integration", totalSales: 1250.75, quantitySold: 42 }],
  topProducts: [
    { productId: "demo-1", productName: "Producto Integracion", quantitySold: 24, totalSales: 479.76 },
    { productId: "demo-2", productName: "Producto CloudShop", quantitySold: 18, totalSales: 770.99 },
  ],
  statuses: [
    { status: "PENDIENTE", orderCount: 4 },
    { status: "CONFIRMADO", orderCount: 6 },
    { status: "EN_PREPARACION", orderCount: 3 },
    { status: "ENVIADO", orderCount: 3 },
    { status: "ENTREGADO", orderCount: 2 },
  ],
  products: [
    { productId: "demo-1", name: "Producto Integracion", category: "testing", price: 19.99, inventory: 5 },
    { productId: "demo-2", name: "Producto CloudShop", category: "cloud", price: 42.5, inventory: 0 },
  ],
  storesList: [
    { storeId: "store-integration", name: "Tienda Integracion", contactEmail: "owner@example.com", status: "ACTIVE" },
    { storeId: "store-demo", name: "Tienda Demo", contactEmail: "demo@example.com", status: "ACTIVE" },
  ],
  orders: [
    { orderId: "pedido-demo-001", status: "PENDIENTE", total: 39.98, createdAt: "2026-07-11T00:00:00Z" },
    { orderId: "pedido-demo-002", status: "ENTREGADO", total: 85, createdAt: "2026-07-11T00:05:00Z" },
  ],
};

const routes = [
  ["dashboard", "Dashboard"],
  ["products", "Productos"],
  ["stores", "Tiendas"],
  ["cart", "Carrito"],
  ["orders", "Pedidos"],
];

function money(value) {
  const amount = Number(value || 0);
  return amount.toLocaleString("es-SV", { style: "currency", currency: "USD" });
}

function saveSession(session) {
  state.session = session;
  localStorage.setItem("cloudshop-session", JSON.stringify(session));
}

function saveCart() {
  localStorage.setItem("cloudshop-cart", JSON.stringify(state.cart));
}

async function request(apiName, path) {
  const baseUrl = config.apis[apiName];
  if (!baseUrl) {
    throw new Error(`API ${apiName} no configurada`);
  }
  if (!config.liveApi) {
    throw new Error("API protegida por AWS_IAM");
  }
  const response = await fetch(`${baseUrl}${path}`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  const payload = await response.json();
  return payload.data || payload;
}

function view(title, body) {
  app.innerHTML = `
    <div class="app-shell">
      <aside class="sidebar">
        <div class="brand"><span class="brand-mark">C</span><span>CloudShop</span></div>
        <nav class="nav">
          ${routes.map(([id, label]) => `<button class="${state.route === id ? "active" : ""}" data-route="${id}">${label}</button>`).join("")}
        </nav>
      </aside>
      <section class="content">
        <header class="topbar">
          <div>
            <h1>${title}</h1>
            <p>${config.environment}${config.liveApi ? "" : " · demo"}</p>
          </div>
          <div class="user-pill">
            <span>${state.session?.name || "Ejecutivo"}</span>
            <button class="btn secondary" data-logout>Salir</button>
          </div>
        </header>
        ${body}
      </section>
    </div>
  `;
}

function renderLogin() {
  app.innerHTML = `
    <div class="login-shell">
      <section class="login-panel">
        <div class="brand"><span class="brand-mark">C</span><span>CloudShop Enterprise</span></div>
        <div>
          <h1>Centro operativo</h1>
          <p>Gestión comercial, inventario, pedidos y métricas ejecutivas en una experiencia ligera.</p>
        </div>
        <form class="form" data-login-form>
          <label class="field">
            <span>Usuario</span>
            <input name="name" value="Administrador" autocomplete="name" />
          </label>
          <label class="field">
            <span>Rol</span>
            <select name="role">
              <option>Administrador</option>
              <option>Operador</option>
              <option>Cliente</option>
            </select>
          </label>
          <button class="btn" type="submit">Entrar</button>
        </form>
      </section>
      <section class="login-visual">
        <div class="login-copy">
          <h1>CloudShop Enterprise</h1>
          <p>Una vitrina funcional para el backend serverless desplegado con AWS, Terraform, API Gateway, Lambda y DynamoDB.</p>
        </div>
      </section>
    </div>
  `;
}

async function renderDashboard() {
  view("Dashboard", `<section class="page"><div class="grid" data-metrics></div><div class="two-col"><div class="table-card" data-best></div><div class="table-card" data-status></div></div></section>`);
  const metrics = app.querySelector("[data-metrics]");
  const best = app.querySelector("[data-best]");
  const status = app.querySelector("[data-status]");
  try {
    const [sales, stores, topProducts, statuses] = await Promise.all([
      request("reportes", "/reportes/ventas/totales"),
      request("reportes", "/reportes/ventas/tiendas?limit=1"),
      request("reportes", "/reportes/productos/mas-vendidos?limit=5"),
      request("reportes", "/reportes/pedidos/estados"),
    ]);
    metrics.innerHTML = `
      <article class="card metric"><span>Ventas totales</span><strong>${money(sales.totalSales)}</strong></article>
      <article class="card metric"><span>Pedidos</span><strong>${sales.orderCount || 0}</strong></article>
      <article class="card metric"><span>Tienda lider</span><strong>${stores[0]?.storeId || "N/A"}</strong></article>
      <article class="card metric"><span>Productos top</span><strong>${topProducts.length || 0}</strong></article>
    `;
    best.innerHTML = table(["Producto", "Unidades", "Ventas"], topProducts.map((item) => [item.productName || item.productId, item.quantitySold, money(item.totalSales)]));
    status.innerHTML = table(["Estado", "Pedidos"], statuses.map((item) => [statusBadge(item.status), item.orderCount]));
  } catch (error) {
    const sales = demoData.sales;
    const stores = demoData.stores;
    const topProducts = demoData.topProducts;
    const statuses = demoData.statuses;
    metrics.innerHTML = `
      <article class="card metric"><span>Ventas totales</span><strong>${money(sales.totalSales)}</strong></article>
      <article class="card metric"><span>Pedidos</span><strong>${sales.orderCount || 0}</strong></article>
      <article class="card metric"><span>Tienda lider</span><strong>${stores[0]?.storeId || "N/A"}</strong></article>
      <article class="card metric"><span>Productos top</span><strong>${topProducts.length || 0}</strong></article>
    `;
    best.innerHTML = table(["Producto", "Unidades", "Ventas"], topProducts.map((item) => [item.productName || item.productId, item.quantitySold, money(item.totalSales)]));
    status.innerHTML = table(["Estado", "Pedidos"], statuses.map((item) => [statusBadge(item.status), item.orderCount]));
  }
}

async function renderProducts() {
  view("Productos", `<section class="page"><div class="toolbar"><h2>Catálogo</h2><button class="btn secondary" data-refresh>Actualizar</button></div><div class="table-card" data-products></div></section>`);
  const target = app.querySelector("[data-products]");
  try {
    const data = await request("productos", "/productos");
    target.innerHTML = table(["Producto", "Categoría", "Precio", "Inventario"], data.map((item) => [
      item.name || item.productId,
      item.category || "N/A",
      money(item.price),
      item.inventory === 0 ? `<span class="badge danger">Sin stock</span>` : `<span class="badge ok">${item.inventory}</span>`,
    ]));
  } catch (error) {
    target.innerHTML = table(["Producto", "Categoría", "Precio", "Inventario"], demoData.products.map((item) => [
      item.name || item.productId,
      item.category || "N/A",
      money(item.price),
      item.inventory === 0 ? `<span class="badge danger">Sin stock</span>` : `<span class="badge ok">${item.inventory}</span>`,
    ]));
  }
}

async function renderStores() {
  view("Tiendas", `<section class="page"><div class="toolbar"><h2>Tiendas</h2><button class="btn secondary" data-refresh>Actualizar</button></div><div class="table-card" data-stores></div></section>`);
  const target = app.querySelector("[data-stores]");
  try {
    const data = await request("tiendas", "/tiendas");
    target.innerHTML = table(["Tienda", "Contacto", "Estado"], data.map((item) => [
      item.name || item.storeId,
      item.contactEmail || "N/A",
      statusBadge(item.status || "ACTIVE"),
    ]));
  } catch (error) {
    target.innerHTML = table(["Tienda", "Contacto", "Estado"], demoData.storesList.map((item) => [
      item.name || item.storeId,
      item.contactEmail || "N/A",
      statusBadge(item.status || "ACTIVE"),
    ]));
  }
}

function renderCart() {
  const total = state.cart.reduce((sum, item) => sum + item.price * item.quantity, 0);
  view("Carrito", `
    <section class="two-col">
      <div class="table-card">
        ${table(["Producto", "Cantidad", "Subtotal"], state.cart.map((item) => [item.name, item.quantity, money(item.price * item.quantity)]))}
      </div>
      <aside class="panel">
        <h2>Resumen</h2>
        <div class="metric"><span>Total</span><strong>${money(total)}</strong></div>
        <button class="btn" data-seed-cart>Agregar muestra</button>
        <button class="btn secondary" data-clear-cart>Vaciar</button>
      </aside>
    </section>
  `);
}

async function renderOrders() {
  const userId = state.session?.userId || "demo-user";
  view("Pedidos", `<section class="page"><div class="toolbar"><h2>Pedidos recientes</h2><button class="btn secondary" data-refresh>Actualizar</button></div><div class="table-card" data-orders></div></section>`);
  const target = app.querySelector("[data-orders]");
  try {
    const data = await request("pedidos", `/usuarios/${encodeURIComponent(userId)}/pedidos`);
    target.innerHTML = table(["Pedido", "Estado", "Total", "Fecha"], data.map((item) => [
      item.orderId,
      statusBadge(item.status),
      money(item.total),
      item.createdAt || "N/A",
    ]));
  } catch (error) {
    target.innerHTML = table(["Pedido", "Estado", "Total", "Fecha"], demoData.orders.map((item) => [
      item.orderId,
      statusBadge(item.status),
      money(item.total),
      item.createdAt || "N/A",
    ]));
  }
}

function table(headers, rows) {
  if (!rows.length) {
    return `<div class="empty">Sin registros</div>`;
  }
  return `
    <table>
      <thead><tr>${headers.map((header) => `<th>${header}</th>`).join("")}</tr></thead>
      <tbody>${rows.map((row) => `<tr>${row.map((cell) => `<td>${cell}</td>`).join("")}</tr>`).join("")}</tbody>
    </table>
  `;
}

function statusBadge(status) {
  const normalized = String(status || "N/A").toUpperCase();
  const tone = normalized.includes("CANCEL") || normalized.includes("DISABLED") ? "danger" : normalized.includes("PEND") ? "warn" : "ok";
  return `<span class="badge ${tone}">${normalized}</span>`;
}

function navigate(route) {
  state.route = state.session ? route : "login";
  render();
}

function render() {
  if (!state.session || state.route === "login") {
    renderLogin();
    return;
  }
  if (state.route === "dashboard") renderDashboard();
  if (state.route === "products") renderProducts();
  if (state.route === "stores") renderStores();
  if (state.route === "cart") renderCart();
  if (state.route === "orders") renderOrders();
}

document.addEventListener("click", (event) => {
  const routeButton = event.target.closest("[data-route]");
  if (routeButton) navigate(routeButton.dataset.route);
  if (event.target.closest("[data-logout]")) {
    localStorage.removeItem("cloudshop-session");
    state.session = null;
    state.route = "login";
    render();
  }
  if (event.target.closest("[data-refresh]")) render();
  if (event.target.closest("[data-seed-cart]")) {
    state.cart.push({ name: "Producto demo", quantity: 1, price: 29.99 });
    saveCart();
    renderCart();
  }
  if (event.target.closest("[data-clear-cart]")) {
    state.cart = [];
    saveCart();
    renderCart();
  }
});

document.addEventListener("submit", (event) => {
  const form = event.target.closest("[data-login-form]");
  if (!form) return;
  event.preventDefault();
  const data = new FormData(form);
  saveSession({
    name: data.get("name") || "Administrador",
    role: data.get("role") || "Administrador",
    userId: "demo-user",
  });
  state.route = "dashboard";
  render();
});

if (state.session) {
  state.route = "dashboard";
}

render();
