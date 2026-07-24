import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Link,
  Navigate,
  Route,
  Routes,
  useLocation,
  useNavigate
} from "react-router-dom";
import { useApi } from "./api/ApiContext";
import { useAuth } from "./auth/AuthContext";
import { homeForRole, ROLES } from "./auth/roles";

const NEXT_ORDER_STATE = {
  PENDIENTE: "CONFIRMADO",
  CONFIRMADO: "EN_PREPARACION",
  EN_PREPARACION: "ENVIADO",
  ENVIADO: "ENTREGADO"
};

const DASHBOARD_METRICS = [
  ["Total de ventas", "/reportes/ventas/total"],
  ["Ventas por tienda", "/reportes/ventas/por-tienda"],
  ["Productos más vendidos", "/reportes/productos/mas-vendidos"],
  ["Productos agotados", "/reportes/productos/agotados"],
  ["Clientes con más compras", "/reportes/clientes/mas-compras"],
  ["Pedidos por estado", "/reportes/pedidos/por-estado"]
];

function messageFor(error) {
  if (!error) return "";
  const reference = error.correlationId
    ? ` Referencia: ${error.correlationId}.`
    : "";
  return `${error.message || "Ocurrió un error."}${reference}`;
}

function useCollection(path) {
  const request = useApi();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result = await request(path);
      setItems(result?.data || []);
    } catch (requestError) {
      setError(messageFor(requestError));
    } finally {
      setLoading(false);
    }
  }, [path, request]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { items, loading, error, refresh };
}

function Feedback({ error, success }) {
  return (
    <>
      {error ? <p className="alert alert-error" role="alert">{error}</p> : null}
      {success ? <p className="alert alert-success" role="status">{success}</p> : null}
    </>
  );
}

function PageState({ loading, error, empty, children }) {
  if (loading) return <p className="page-state">Cargando datos reales…</p>;
  if (error) return <Feedback error={error} />;
  if (empty) return <p className="page-state">No hay registros para mostrar.</p>;
  return children;
}

function SubmitButton({ busy, children }) {
  return <button disabled={busy} type="submit">{busy ? "Procesando…" : children}</button>;
}

function AuthPage() {
  const { status, login, register, confirmRegistration, authError, session } =
    useAuth();
  const navigate = useNavigate();
  const [mode, setMode] = useState("login");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [pendingEmail, setPendingEmail] = useState("");

  if (status === "authenticated") {
    return <Navigate replace to={homeForRole(session.role)} />;
  }

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    const form = new FormData(event.currentTarget);
    try {
      if (mode === "login") {
        await login(form.get("email"), form.get("password"));
        navigate("/");
      } else if (mode === "register") {
        const email = form.get("email");
        await register(form.get("name"), email, form.get("password"));
        setPendingEmail(email);
        setMode("confirm");
        setNotice("Cuenta creada como CLIENTE. Revisa tu correo para confirmarla.");
      } else {
        await confirmRegistration(form.get("email"), form.get("code"));
        setMode("login");
        setNotice("Cuenta confirmada. Ya puedes iniciar sesión.");
      }
    } catch (submitError) {
      setError(messageFor(submitError));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth-shell">
      <section className="auth-card">
        <Link className="brand auth-brand" to="/">CloudShop</Link>
        <p className="eyebrow">Enterprise commerce</p>
        <h1>
          {mode === "login"
            ? "Bienvenido"
            : mode === "register"
              ? "Crea tu cuenta"
              : "Confirma tu correo"}
        </h1>
        <p className="muted">
          {mode === "register"
            ? "Todo registro nuevo recibe únicamente el rol CLIENTE."
            : "Acceso protegido con Cognito y credenciales temporales."}
        </p>
        <Feedback error={error || authError} success={notice} />
        <form onSubmit={submit}>
          {mode === "register" ? (
            <label>Nombre<input name="name" required maxLength="160" /></label>
          ) : null}
          <label>
            Correo
            <input
              defaultValue={pendingEmail}
              name="email"
              type="email"
              autoComplete="email"
              required
            />
          </label>
          {mode === "confirm" ? (
            <label>Código<input name="code" inputMode="numeric" required /></label>
          ) : (
            <label>
              Contraseña
              <input
                name="password"
                type="password"
                autoComplete={mode === "login" ? "current-password" : "new-password"}
                minLength="8"
                required
              />
            </label>
          )}
          <SubmitButton busy={busy}>
            {mode === "login" ? "Ingresar" : mode === "register" ? "Registrarme" : "Confirmar"}
          </SubmitButton>
        </form>
        <div className="auth-actions">
          {mode !== "login" ? (
            <button className="link-button" onClick={() => setMode("login")} type="button">
              Volver al ingreso
            </button>
          ) : (
            <button className="link-button" onClick={() => setMode("register")} type="button">
              Crear cuenta CLIENTE
            </button>
          )}
        </div>
      </section>
    </main>
  );
}

function navFor(role) {
  if (role === ROLES.ADMINISTRADOR) {
    return [
      ["/admin/dashboard", "Dashboard"],
      ["/admin/usuarios", "Usuarios"],
      ["/admin/tiendas", "Tiendas"],
      ["/admin/productos", "Productos"]
    ];
  }
  if (role === ROLES.OPERADOR) {
    return [
      ["/operador/pedidos", "Pedidos"],
      ["/operador/inventario", "Inventario"]
    ];
  }
  return [
    ["/productos", "Productos"],
    ["/carrito", "Carrito"],
    ["/pedidos", "Mis pedidos"]
  ];
}

function Layout({ children }) {
  const { session, logout } = useAuth();
  const location = useLocation();
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Link className="brand" to={homeForRole(session.role)}>CloudShop</Link>
        <div className="identity">
          <span className="avatar">{session.name?.slice(0, 1).toUpperCase()}</span>
          <div><strong>{session.name}</strong><small>{session.role}</small></div>
        </div>
        <nav aria-label="Navegación principal">
          {navFor(session.role).map(([path, label]) => (
            <Link
              className={location.pathname === path ? "active" : ""}
              key={path}
              to={path}
            >
              {label}
            </Link>
          ))}
        </nav>
        <button className="secondary logout" onClick={logout} type="button">Cerrar sesión</button>
      </aside>
      <main className="content">{children}</main>
    </div>
  );
}

function Protected({ roles, children }) {
  const { status, session } = useAuth();
  if (status === "loading") return <main className="centered">Restaurando sesión segura…</main>;
  if (status !== "authenticated") return <Navigate replace to="/acceso" />;
  if (roles && !roles.includes(session.role)) {
    return <Navigate replace to={homeForRole(session.role)} />;
  }
  return <Layout>{children}</Layout>;
}

function PageHeader({ eyebrow, title, description, action }) {
  return (
    <header className="page-header">
      <div><p className="eyebrow">{eyebrow}</p><h1>{title}</h1><p>{description}</p></div>
      {action}
    </header>
  );
}

function ProductCard({ product, onAdd, busy }) {
  return (
    <article className="card product-card">
      <span className="pill">{product.category}</span>
      <h2>{product.name}</h2>
      <p>{product.description}</p>
      <dl className="card-data">
        <div><dt>Código</dt><dd>{product.code}</dd></div>
        <div><dt>Disponibles</dt><dd>{product.inventory}</dd></div>
      </dl>
      <div className="card-footer">
        <strong>${Number(product.price).toFixed(2)}</strong>
        <button disabled={busy || Number(product.inventory) < 1} onClick={() => onAdd(product)} type="button">
          Agregar
        </button>
      </div>
    </article>
  );
}

function CatalogPage() {
  const request = useApi();
  const products = useCollection("/productos");
  const [busyId, setBusyId] = useState("");
  const [feedback, setFeedback] = useState({ error: "", success: "" });

  async function add(product) {
    setBusyId(product.productId);
    setFeedback({ error: "", success: "" });
    try {
      await request("/carritos/mio/items", {
        method: "POST",
        body: { productId: product.productId, quantity: 1 }
      });
      setFeedback({ error: "", success: `${product.name} se agregó al carrito.` });
    } catch (error) {
      setFeedback({ error: messageFor(error), success: "" });
    } finally {
      setBusyId("");
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Catálogo protegido"
        title="Productos"
        description="Inventario real disponible para tu compra."
      />
      <Feedback {...feedback} />
      <PageState loading={products.loading} error={products.error} empty={!products.items.length}>
        <section className="card-grid">
          {products.items.map((product) => (
            <ProductCard
              busy={busyId === product.productId}
              key={product.productId}
              onAdd={add}
              product={product}
            />
          ))}
        </section>
      </PageState>
    </>
  );
}

function CartPage() {
  const request = useApi();
  const [cart, setCart] = useState(null);
  const [products, setProducts] = useState({});
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const [feedback, setFeedback] = useState({ error: "", success: "" });

  const refresh = useCallback(async () => {
    setLoading(true);
    setFeedback({ error: "", success: "" });
    try {
      const [cartResult, productResult] = await Promise.all([
        request("/carritos/mio"),
        request("/productos")
      ]);
      setCart(cartResult.data);
      setProducts(
        Object.fromEntries((productResult.data || []).map((item) => [item.productId, item]))
      );
    } catch (error) {
      setFeedback({ error: messageFor(error), success: "" });
    } finally {
      setLoading(false);
    }
  }, [request]);

  useEffect(() => { refresh(); }, [refresh]);

  async function mutate(label, path, options) {
    setBusy(label);
    setFeedback({ error: "", success: "" });
    try {
      const result = await request(path, options);
      if (result?.data) setCart(result.data);
      else await refresh();
    } catch (error) {
      setFeedback({ error: messageFor(error), success: "" });
    } finally {
      setBusy("");
    }
  }

  async function checkout() {
    setBusy("checkout");
    setFeedback({ error: "", success: "" });
    try {
      const result = await request("/pedidos", {
        method: "POST",
        headers: { "Idempotency-Key": crypto.randomUUID() }
      });
      setCart({ ...cart, items: [] });
      setFeedback({
        error: "",
        success: `Pedido ${result.data.orderId} creado en estado PENDIENTE.`
      });
    } catch (error) {
      setFeedback({ error: messageFor(error), success: "" });
    } finally {
      setBusy("");
    }
  }

  const items = cart?.items || [];
  const total = items.reduce((sum, item) => {
    return sum + Number(products[item.productId]?.price || 0) * item.quantity;
  }, 0);

  return (
    <>
      <PageHeader eyebrow="Compra" title="Tu carrito" description="Las cantidades se guardan en CloudShop." />
      <Feedback {...feedback} />
      <PageState loading={loading} error="" empty={!items.length}>
        <section className="panel">
          {items.map((item) => {
            const product = products[item.productId] || {};
            return (
              <div className="cart-row" key={item.productId}>
                <div><strong>{product.name || item.productId}</strong><small>${Number(product.price || 0).toFixed(2)} c/u</small></div>
                <label>
                  Cantidad
                  <input
                    aria-label={`Cantidad de ${product.name || item.productId}`}
                    defaultValue={item.quantity}
                    min="1"
                    max="99"
                    onBlur={(event) => {
                      const quantity = Number(event.target.value);
                      if (quantity !== item.quantity) {
                        mutate(item.productId, `/carritos/mio/items/${item.productId}`, {
                          method: "PATCH",
                          body: { quantity }
                        });
                      }
                    }}
                    type="number"
                  />
                </label>
                <strong>${(Number(product.price || 0) * item.quantity).toFixed(2)}</strong>
                <button
                  className="danger secondary"
                  disabled={busy === item.productId}
                  onClick={() =>
                    mutate(item.productId, `/carritos/mio/items/${item.productId}`, {
                      method: "DELETE"
                    })
                  }
                  type="button"
                >
                  Eliminar
                </button>
              </div>
            );
          })}
          <div className="checkout-row">
            <button
              className="secondary"
              disabled={Boolean(busy)}
              onClick={() => mutate("clear", "/carritos/mio", { method: "DELETE" })}
              type="button"
            >
              Vaciar carrito
            </button>
            <div><span>Total</span><strong>${total.toFixed(2)}</strong></div>
            <button disabled={Boolean(busy)} onClick={checkout} type="button">
              {busy === "checkout" ? "Creando pedido…" : "Confirmar pedido"}
            </button>
          </div>
        </section>
      </PageState>
    </>
  );
}

function OrdersPage({ operator = false }) {
  const request = useApi();
  const orders = useCollection(operator ? "/pedidos" : "/pedidos/mios");
  const [busy, setBusy] = useState("");
  const [feedback, setFeedback] = useState({ error: "", success: "" });

  async function command(order, kind) {
    setBusy(order.orderId);
    setFeedback({ error: "", success: "" });
    try {
      const path =
        kind === "cancel"
          ? `/pedidos/${order.orderId}/cancelacion`
          : `/pedidos/${order.orderId}/estado`;
      await request(path, {
        method: kind === "cancel" ? "POST" : "PATCH",
        headers: { "Idempotency-Key": crypto.randomUUID() },
        ...(kind === "advance"
          ? { body: { status: NEXT_ORDER_STATE[order.status] } }
          : {})
      });
      setFeedback({ error: "", success: "Pedido actualizado correctamente." });
      await orders.refresh();
    } catch (error) {
      setFeedback({ error: messageFor(error), success: "" });
    } finally {
      setBusy("");
    }
  }

  return (
    <>
      <PageHeader
        eyebrow={operator ? "Operaciones" : "Historial"}
        title={operator ? "Gestión de pedidos" : "Mis pedidos"}
        description={operator ? "Avanza pedidos según la máquina de estados." : "Solo puedes ver y cancelar tus propios pedidos."}
      />
      <Feedback {...feedback} />
      <PageState loading={orders.loading} error={orders.error} empty={!orders.items.length}>
        <section className="table-panel">
          <table>
            <thead><tr><th>Pedido</th>{operator ? <th>Cliente</th> : null}<th>Estado</th><th>Total</th><th>Fecha</th><th>Acción</th></tr></thead>
            <tbody>
              {orders.items.map((order) => (
                <tr key={order.orderId}>
                  <td><code>{order.orderId}</code></td>
                  {operator ? <td><code>{order.customerId}</code></td> : null}
                  <td><span className={`status status-${order.status}`}>{order.status}</span></td>
                  <td>${Number(order.total).toFixed(2)}</td>
                  <td>{new Date(order.createdAt).toLocaleString()}</td>
                  <td className="actions">
                    {operator && NEXT_ORDER_STATE[order.status] ? (
                      <button disabled={busy === order.orderId} onClick={() => command(order, "advance")} type="button">
                        Pasar a {NEXT_ORDER_STATE[order.status]}
                      </button>
                    ) : null}
                    {["PENDIENTE", "CONFIRMADO"].includes(order.status) ? (
                      <button className="secondary danger" disabled={busy === order.orderId} onClick={() => command(order, "cancel")} type="button">
                        Cancelar
                      </button>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </PageState>
    </>
  );
}

function UsersPage() {
  const request = useApi();
  const users = useCollection("/usuarios");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  async function update(user, operation, value) {
    setBusy(user.userId);
    setError("");
    try {
      if (operation === "role") {
        await request(`/usuarios/${user.userId}/rol`, {
          method: "PATCH",
          body: { role: value }
        });
      } else {
        await request(`/usuarios/${user.userId}`, { method: "DELETE" });
      }
      await users.refresh();
    } catch (requestError) {
      setError(messageFor(requestError));
    } finally {
      setBusy("");
    }
  }

  return (
    <>
      <PageHeader eyebrow="Administración" title="Usuarios" description="Los roles privilegiados solo se asignan desde este flujo protegido y auditable." />
      <Feedback error={error} />
      <PageState loading={users.loading} error={users.error} empty={!users.items.length}>
        <section className="table-panel">
          <table>
            <thead><tr><th>Usuario</th><th>Correo</th><th>Estado</th><th>Rol</th><th>Acción</th></tr></thead>
            <tbody>{users.items.map((user) => (
              <tr key={user.userId}>
                <td>{user.name}</td><td>{user.email}</td><td>{user.status}</td>
                <td>
                  <select
                    aria-label={`Rol de ${user.name}`}
                    disabled={busy === user.userId || user.status !== "ACTIVE"}
                    onChange={(event) => update(user, "role", event.target.value)}
                    value={user.role}
                  >
                    {Object.values(ROLES).map((role) => <option key={role}>{role}</option>)}
                  </select>
                </td>
                <td><button className="secondary danger" disabled={busy === user.userId || user.status !== "ACTIVE"} onClick={() => update(user, "deactivate")} type="button">Desactivar</button></td>
              </tr>
            ))}</tbody>
          </table>
        </section>
      </PageState>
    </>
  );
}

function StoreForm({ initial, onSave, onCancel }) {
  const [busy, setBusy] = useState(false);
  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    const form = new FormData(event.currentTarget);
    await onSave({ name: form.get("name"), description: form.get("description") });
    setBusy(false);
  }
  return (
    <form className="inline-form panel" onSubmit={submit}>
      <label>Nombre<input defaultValue={initial?.name} name="name" required maxLength="160" /></label>
      <label className="grow">Descripción<input defaultValue={initial?.description} name="description" required maxLength="1000" /></label>
      <SubmitButton busy={busy}>{initial ? "Guardar" : "Crear tienda"}</SubmitButton>
      {initial ? <button className="secondary" onClick={onCancel} type="button">Cancelar</button> : null}
    </form>
  );
}

function StoresPage() {
  const request = useApi();
  const stores = useCollection("/tiendas?includeInactive=true");
  const [editing, setEditing] = useState(null);
  const [error, setError] = useState("");

  async function save(values) {
    setError("");
    try {
      await request(editing ? `/tiendas/${editing.storeId}` : "/tiendas", {
        method: editing ? "PUT" : "POST",
        body: values
      });
      setEditing(null);
      await stores.refresh();
    } catch (requestError) {
      setError(messageFor(requestError));
    }
  }

  async function deactivate(store) {
    setError("");
    try {
      await request(`/tiendas/${store.storeId}`, { method: "DELETE" });
      await stores.refresh();
    } catch (requestError) {
      setError(messageFor(requestError));
    }
  }

  return (
    <>
      <PageHeader eyebrow="Administración" title="Tiendas" description="Alta, consulta, actualización y desactivación lógica." />
      <StoreForm
        initial={editing}
        key={editing?.storeId || "new-store"}
        onCancel={() => setEditing(null)}
        onSave={save}
      />
      <Feedback error={error} />
      <PageState loading={stores.loading} error={stores.error} empty={!stores.items.length}>
        <section className="card-grid">
          {stores.items.map((store) => (
            <article className="card" key={store.storeId}>
              <span className={`pill ${store.status === "INACTIVE" ? "pill-muted" : ""}`}>{store.status}</span>
              <h2>{store.name}</h2><p>{store.description}</p>
              <div className="actions">
                <button className="secondary" disabled={store.status !== "ACTIVE"} onClick={() => setEditing(store)} type="button">Editar</button>
                <button className="secondary danger" disabled={store.status !== "ACTIVE"} onClick={() => deactivate(store)} type="button">Desactivar</button>
              </div>
            </article>
          ))}
        </section>
      </PageState>
    </>
  );
}

const EMPTY_PRODUCT = {
  code: "",
  name: "",
  description: "",
  category: "",
  price: "",
  inventory: "",
  storeId: ""
};

function ProductForm({ initial = EMPTY_PRODUCT, stores, onSave, onCancel }) {
  const [busy, setBusy] = useState(false);
  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    const form = Object.fromEntries(new FormData(event.currentTarget));
    await onSave({ ...form, price: Number(form.price), inventory: Number(form.inventory) });
    setBusy(false);
  }
  return (
    <form className="product-form panel" onSubmit={submit}>
      <label>Código<input defaultValue={initial.code} name="code" required /></label>
      <label>Nombre<input defaultValue={initial.name} name="name" required /></label>
      <label>Categoría<input defaultValue={initial.category} name="category" required /></label>
      <label>Precio<input defaultValue={initial.price} min="0.01" name="price" required step="0.01" type="number" /></label>
      <label>Inventario<input defaultValue={initial.inventory} min="0" name="inventory" required step="1" type="number" /></label>
      <label>Tienda<select defaultValue={initial.storeId} name="storeId" required><option value="">Selecciona…</option>{stores.map((store) => <option key={store.storeId} value={store.storeId}>{store.name}</option>)}</select></label>
      <label className="wide">Descripción<textarea defaultValue={initial.description} name="description" required rows="2" /></label>
      <SubmitButton busy={busy}>{initial.productId ? "Guardar producto" : "Crear producto"}</SubmitButton>
      {initial.productId ? <button className="secondary" onClick={onCancel} type="button">Cancelar</button> : null}
    </form>
  );
}

function ProductsAdminPage() {
  const request = useApi();
  const products = useCollection("/productos");
  const stores = useCollection("/tiendas");
  const [editing, setEditing] = useState(null);
  const [error, setError] = useState("");

  async function save(values) {
    setError("");
    try {
      await request(editing ? `/productos/${editing.productId}` : "/productos", {
        method: editing ? "PUT" : "POST",
        body: values
      });
      setEditing(null);
      await products.refresh();
    } catch (requestError) {
      setError(messageFor(requestError));
    }
  }

  async function remove(product) {
    setError("");
    try {
      await request(`/productos/${product.productId}`, { method: "DELETE" });
      await products.refresh();
    } catch (requestError) {
      setError(messageFor(requestError));
    }
  }

  return (
    <>
      <PageHeader eyebrow="Administración" title="Productos" description="CRUD con todos los campos obligatorios." />
      <ProductForm
        initial={editing || EMPTY_PRODUCT}
        key={editing?.productId || "new-product"}
        onCancel={() => setEditing(null)}
        onSave={save}
        stores={stores.items}
      />
      <Feedback error={error || stores.error} />
      <PageState loading={products.loading || stores.loading} error={products.error} empty={!products.items.length}>
        <section className="table-panel">
          <table>
            <thead><tr><th>Código</th><th>Producto</th><th>Categoría</th><th>Precio</th><th>Inventario</th><th>Acción</th></tr></thead>
            <tbody>{products.items.map((product) => (
              <tr key={product.productId}>
                <td>{product.code}</td><td>{product.name}</td><td>{product.category}</td>
                <td>${Number(product.price).toFixed(2)}</td><td>{product.inventory}</td>
                <td className="actions"><button className="secondary" onClick={() => setEditing(product)} type="button">Editar</button><button className="secondary danger" onClick={() => remove(product)} type="button">Eliminar</button></td>
              </tr>
            ))}</tbody>
          </table>
        </section>
      </PageState>
    </>
  );
}

function InventoryPage() {
  const request = useApi();
  const products = useCollection("/productos");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  async function save(product, value) {
    setBusy(product.productId);
    setError("");
    try {
      await request(`/productos/${product.productId}/inventario`, {
        method: "PATCH",
        body: { inventory: Number(value) }
      });
      await products.refresh();
    } catch (requestError) {
      setError(messageFor(requestError));
    } finally {
      setBusy("");
    }
  }

  return (
    <>
      <PageHeader eyebrow="Operaciones" title="Inventario" description="Ajustes protegidos sin modificar los demás campos." />
      <Feedback error={error} />
      <PageState loading={products.loading} error={products.error} empty={!products.items.length}>
        <section className="table-panel">
          <table>
            <thead><tr><th>Código</th><th>Producto</th><th>Inventario</th><th>Guardar</th></tr></thead>
            <tbody>{products.items.map((product) => (
              <InventoryRow busy={busy === product.productId} key={product.productId} onSave={(value) => save(product, value)} product={product} />
            ))}</tbody>
          </table>
        </section>
      </PageState>
    </>
  );
}

function InventoryRow({ product, onSave, busy }) {
  const [value, setValue] = useState(product.inventory);
  return (
    <tr>
      <td>{product.code}</td><td>{product.name}</td>
      <td><input aria-label={`Inventario de ${product.name}`} min="0" onChange={(event) => setValue(event.target.value)} type="number" value={value} /></td>
      <td><button disabled={busy || Number(value) === Number(product.inventory)} onClick={() => onSave(value)} type="button">{busy ? "Guardando…" : "Guardar"}</button></td>
    </tr>
  );
}

function DashboardPage() {
  const request = useApi();
  const [metrics, setMetrics] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    Promise.all(
      DASHBOARD_METRICS.map(async ([label, path]) => {
        const result = await request(path);
        return { label, value: result.data };
      })
    )
      .then((result) => { if (active) setMetrics(result); })
      .catch((requestError) => { if (active) setError(messageFor(requestError)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [request]);

  return (
    <>
      <PageHeader eyebrow="Administración" title="Dashboard ejecutivo" description="Las seis métricas oficiales, exclusivas para ADMINISTRADOR." />
      <PageState loading={loading} error={error} empty={false}>
        <section className="metric-grid">
          {metrics.map((metric) => (
            <article className="metric-card" key={metric.label}>
              <h2>{metric.label}</h2>
              {typeof metric.value === "number" || typeof metric.value === "string"
                ? <strong>{metric.value}</strong>
                : <pre>{JSON.stringify(metric.value, null, 2)}</pre>}
            </article>
          ))}
        </section>
      </PageState>
    </>
  );
}

function HomeRedirect() {
  const { status, session } = useAuth();
  if (status === "loading") return <main className="centered">Restaurando sesión segura…</main>;
  return <Navigate replace to={status === "authenticated" ? homeForRole(session.role) : "/acceso"} />;
}

function NotFound() {
  const { session } = useAuth();
  return (
    <section className="not-found"><p className="eyebrow">404</p><h1>Ruta no encontrada</h1>
      <Link to={homeForRole(session.role)}>Volver al inicio</Link>
    </section>
  );
}

export default function App() {
  return (
    <Routes>
      <Route element={<AuthPage />} path="/acceso" />
      <Route element={<HomeRedirect />} path="/" />
      <Route element={<Protected roles={[ROLES.CLIENTE]}><CatalogPage /></Protected>} path="/productos" />
      <Route element={<Protected roles={[ROLES.CLIENTE]}><CartPage /></Protected>} path="/carrito" />
      <Route element={<Protected roles={[ROLES.CLIENTE]}><OrdersPage /></Protected>} path="/pedidos" />
      <Route element={<Protected roles={[ROLES.ADMINISTRADOR]}><DashboardPage /></Protected>} path="/admin/dashboard" />
      <Route element={<Protected roles={[ROLES.ADMINISTRADOR]}><UsersPage /></Protected>} path="/admin/usuarios" />
      <Route element={<Protected roles={[ROLES.ADMINISTRADOR]}><StoresPage /></Protected>} path="/admin/tiendas" />
      <Route element={<Protected roles={[ROLES.ADMINISTRADOR]}><ProductsAdminPage /></Protected>} path="/admin/productos" />
      <Route element={<Protected roles={[ROLES.OPERADOR]}><OrdersPage operator /></Protected>} path="/operador/pedidos" />
      <Route element={<Protected roles={[ROLES.OPERADOR]}><InventoryPage /></Protected>} path="/operador/inventario" />
      <Route element={<Protected><NotFound /></Protected>} path="*" />
    </Routes>
  );
}
