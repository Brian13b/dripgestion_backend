# Auditoría del backend — hallazgos (sin corregir)

Fecha: 2026-11-19. Alcance: `app/` (FastAPI + SQLAlchemy). **No se modificó código de producción.**
Cada hallazgo con ID `BUG-xx` tiene al menos un test marcado `xfail(strict=True)` que describe el
comportamiento correcto: cuando se corrija el bug, el test pasa y pytest avisa para quitar la marca.
Buscar el ID con `pytest -k` no sirve (va en la razón del xfail); usar `pytest -rx` para listarlos.

## Estado de las correcciones (rama `fix/backend-criticos`)
| ID | Estado | Cómo quedó |
|---|---|---|
| BUG-23 | Corregido | `FIRST_SUPERADMIN_PASSWORD` ya no tiene valor por defecto: sin ella (o con menos de 10 caracteres) no se crea el superadmin. `seed_superadmin.py` también la toma del entorno. |
| BUG-02 | Corregido | Nueva dependencia `get_current_staff` (admin y repartidor): clientes, catálogo, recorridos, movimientos, pagos e historial dejan de aceptar usuarios CLIENTE o superadmin. |
| BUG-03 | Corregido | Un admin solo puede asignar `admin` o `repartidor`; los usuarios CLIENTE ya no se pueden ver, editar ni borrar desde `/users`. |
| BUG-01 | Corregido | `crud_user` guarda `hashed_password`. `tenant_id` pasó a opcional e ignorado en `UserCreate` (el front nunca lo enviaba y recibía 422); la empresa sale del admin autenticado. |
| BUG-04 | Corregido | Resetear la contraseña por `PUT /users` la hashea en `hashed_password` y cierra las sesiones del usuario. |
| BUG-16 (parcial) | Corregido solo "desasignar chofer" | `PATCH /recorridos/{id}/asignar-repartidor` acepta `repartidor_id: null`. Siguen pendientes los 500 al eliminar una ruta con movimientos. |
| BUG-18 | Corregido | Montos y cantidades no negativos, pago manual > 0, cantidades enteras; el total no puede superar el valor del catálogo (puede ser menor: descuentos) **y, con el detalle vacío (o todo en 0), un total positivo se rechaza con 400** (el respaldo de ítems es 0). Total 0 con detalle vacío sigue siendo válido (visita sin venta / devolución). |
| BUG-17 | Corregido, **requiere migración** | Decisión de producto aprobada: el repartidor puede atender clientes fuera de su recorrido **dentro de su misma empresa**, pero como **visita excepcional explícita**. Cliente y recorrido se buscan siempre por `tenant_id` (otra empresa → 404). Con `recorrido_id` y un cliente que no está en ese recorrido, el repartidor debe mandar `visita_excepcional: true` (si no, 403). El movimiento queda con `visita_excepcional=true` (columna nueva, migración `c5d8a1f3e2b7`) y la observación con el prefijo `[Visita excepcional]`; el admin fuera de ruta también queda marcado. Se ve en `GET /logistica/historial` (campo `visita_excepcional`) y en `GET /logistica/historial/mes-actual` (`visitas_excepcionales` y `cobrado_en_visitas_excepcionales`, ya incluido en efectivo/transferencia). Sin `recorrido_id` y para pagos manuales el repartidor sigue limitado a sus rutas. |
| BUG-21 | Corregido | Una entrega a cuenta corriente no puede traer monto cobrado (422): el cobro parcial se declara con su método y suma en la caja. El pago manual solo acepta `efectivo` o `transferencia`. |
| BUG-19 | Mitigado | Los saldos, totales y cobros se redondean a centavos (mitad hacia arriba) al escribir, y los totales de caja/dashboard al leer: 0.3 − 0.1 − 0.2 ahora da exactamente 0. **La columna sigue siendo `Float`**: pasar a `Numeric(12,2)` requiere migración y revisar todos los cálculos; queda como endurecimiento posterior. |
| BUG-07 | Corregido (sin baja lógica) | Eliminar un cliente con movimientos responde 409 con un mensaje claro y conserva todo; los clientes sin historial se siguen pudiendo borrar. Una baja lógica (cliente "archivado") queda como mejora. |
| BUG-10 | Corregido, **requiere migración** | `users.username` es único por empresa (`tenant_id, username`) y para superadmin con índice parcial. El login busca dentro de la empresa indicada. Migración `a3c91e2d7b10` (aplicar con `alembic upgrade head`; el SQL está validado en modo offline, no se aplicó a ninguna base). El alta de empresa ya no rechaza un admin con username usado en otra empresa. |
| BUG-20 | Corregido | `metodo_pago` del pago manual validado (422). Códigos alineados en entregas **y** pagos manuales: sin permiso → **403** (`PermisoDenegado`), cliente/recorrido inexistente o de otra empresa → **404** (`NoEncontrado`), clave de idempotencia reutilizada → 409, resto de validaciones de negocio → 400. |
| Paleta de empresas nuevas | Corregido, **requiere migración (opcional)** | Las empresas nuevas nacían con la paleta azul (`#25A7DA`…). Ahora la paleta única está en `app/core/branding.py` (naranja `#E86A1F` + arena, la misma del front) y la usan el modelo, los schemas y el alta. La migración `d2f6b9a47c13` actualiza solo las empresas que seguían con **todos** los colores azules por defecto (no toca las que eligieron los suyos). |
| Riesgo 1: zona horaria | Corregido | Nuevo `app/core/timezone.py` (`APP_TIMEZONE`, por defecto `America/Argentina/Buenos_Aires`). "Hoy", el día de caja, el mes y el año se calculan en hora local con rangos `[inicio, fin)` en UTC; las agrupaciones por mes y por día se hacen en Python (portables entre PostgreSQL y SQLite). Las horas y fechas que se muestran (historial, portal) salen en hora local. Se agregó `tzdata` a `requirements.txt` (Windows no trae base de zonas horarias). |
| Riesgo 2: idempotencia | Corregido, **requiere migración** | `POST /logistica/movimientos` y `/movimientos/pago/{id}` aceptan el header `Idempotency-Key`: un reintento devuelve lo ya registrado sin duplicar deuda, envases ni movimiento; la misma clave para otro cliente da 409; la clave es por empresa; restricción única `(tenant_id, idempotency_key)` como red de seguridad en carreras. Migración `b7e24f90c1a5`. El front la envía en entregas y cobros. Sin el header todo funciona como antes. |
| Riesgo 3: concurrencia | Corregido, **no verificado en un PostgreSQL real** | El cliente se lee con bloqueo de fila (`SELECT … FOR UPDATE`) en entregas y pagos manuales, así las operaciones simultáneas sobre el mismo cliente se ejecutan en orden. La consulta se verifica compilada para PostgreSQL. SQLite no tiene bloqueo de fila (ahí la prueba de carga **sí** pierde actualizaciones, lo que confirma el riesgo), por eso ese test corre solo con `TEST_DATABASE_URL`. |
| Riesgos 1–3: revisión de cobertura (Bloque A) | Revisado | Zona horaria: ya cubierta (día/mes/año, dashboard, portal, `hoy`). Idempotencia: se agregaron tests de que los reintentos **no inflan el cierre de caja ni el historial** y de que un reintento de visita excepcional se cuenta una sola vez. Concurrencia: sin cambios; sigue pendiente correr la suite con `TEST_DATABASE_URL` sobre un PostgreSQL real. Sigue abierto el riesgo 4 (envases recortados a 0). |
El resto de los hallazgos sigue abierto.

## Críticos
| ID | Dónde | Qué pasa |
|---|---|---|
| BUG-01 | `crud/crud_user.py:13` | `POST /users` siempre da 500: crea `User(password=...)` y la columna es `hashed_password`. No se pueden dar de alta repartidores desde la app. |
| BUG-02 | `controllers/clientes.py`, `logistica.py` (GET recorridos/{id}) | Los endpoints usan `get_current_user`: un usuario con rol CLIENTE (portal) puede listar todos los clientes de la empresa (saldos, teléfonos, direcciones), editarlos, cambiar PINs, **eliminarlos** y crear clientes. |
| BUG-03 | `schemas/user.py`, `crud_user.update_user_within_tenant` | Un admin de empresa puede ponerle `role: "superadmin"` a un usuario y ese usuario obtiene acceso a `/tenants/` (todas las empresas). Verificado de punta a punta. |
| BUG-18 | `schemas/logistica.py`, `logistica_service.py` | Montos negativos aceptados (`monto_total`, `monto_cobrado`, pago manual, cantidades de envases). El total lo manda el cliente y no se contrasta con el catálogo. Un movimiento puede bajar una deuda sin cobrar. |
| BUG-23 | `core/config.py`, `.env` | El superadmin se crea con contraseña por defecto escrita en el código (`Superadmin123!`) si no se define `FIRST_SUPERADMIN_PASSWORD`. Además dos líneas del `.env` están mal formadas (`FIRST_SUPERADMIN_USER: str`), python-dotenv las ignora y se usan los defaults. |

## Altos
| ID | Dónde | Qué pasa |
|---|---|---|
| BUG-04 | `crud_user.update_user_within_tenant` | Editar la contraseña de un usuario no la cambia (hace `setattr(user, "password", hash)` sobre algo que no es columna) y tampoco cierra sus sesiones. Falla en silencio. |
| BUG-07 | `cliente_service.eliminar_cliente` | Borrar un cliente con movimientos viola la FK (500). Si la FK no existiera, se perdería el historial contable. Falta baja lógica. |
| BUG-10 | `models/user.py` + `cliente_service.crear_cliente_con_acceso` | `users.username` es único global pero se valida por empresa. El mismo teléfono como cliente en dos distribuidoras da 500: bloquea el modelo multi-empresa. |
| BUG-17 | `logistica_service.registrar_entrega` | Si el repartidor manda su propio `recorrido_id`, no se valida que el cliente esté en esa ruta: puede operar con cualquier cliente de la empresa. La validación solo corre cuando NO hay `recorrido_id`. |
| BUG-19 | `models/cliente.py`, `logistica.py` | Dinero en `Float`. Ejemplo reproducido: 0.3 − 0.1 − 0.2 deja −2.8e-17 en vez de 0. Debe ser `Numeric`/centavos enteros. |
| BUG-21 | `logistica_service.obtener_resumen_mes`, `dashboard_service` | El cobro parcial de una entrega a cuenta corriente no cuenta ni en efectivo ni en transferencia: el cierre de caja no suma lo realmente cobrado. En el dashboard "A Cuenta" suma el total de la venta aunque se haya cobrado una parte. |

## Medios
| ID | Dónde | Qué pasa |
|---|---|---|
| BUG-05 | `UserUpdate` | `username: null` explícito da 500. |
| BUG-06 | `crud_user.delete_user` | Borrar un repartidor con recorridos/movimientos da 500; un admin puede borrarse a sí mismo. |
| BUG-08 | `crud_logistica.create_recorrido`, `PUT recorridos` | `repartidor_id` y `clientes_orden` no se validan contra la empresa: se aceptan IDs de otra empresa. |
| BUG-09 | `controllers/tenants.py` | (a) el admin puede cambiar su `subdominio` por uno existente → 500; (b) el chequeo de subdominio repetido en el alta no normaliza mayúsculas → 500; (c) subdominio y colores/fuente sin validar (se inyectan luego en el CSS del front); (d) el superadmin no puede editar una empresa suspendida (404). |
| BUG-11 | `schemas/cliente.py` | CUIT sin validar (largo, dígitos, verificador); `limit` de paginación sin tope ni mínimo; `direccion: null` → 500; el PIN se guarda también en texto plano en `clientes.pin_acceso` y el default es `1234`. |
| BUG-13 | `PasswordUpdate`, onboarding | Sin política de contraseña (se acepta `"1"`). |
| BUG-15 | `schemas/producto.py` | Precios y valores de reposición negativos; nombre/código vacíos; se pueden entregar productos inactivos. |
| BUG-16 | `delete_recorrido`, `asignar-repartidor` | Eliminar una ruta con movimientos → 500; no se puede desasignar un repartidor (el schema exige `int`). |
| BUG-20 | `controllers/logistica.py` | Pago manual: todo `ValueError` sale como 404 (incluida la falta de permisos, que debería ser 403) y `metodo_pago` es `str` libre. |
| BUG-24 | `main.py` | CORS con regex `*.vercel.app` + `allow_credentials=True`: cualquier sitio alojado en Vercel puede llamar a la API desde el navegador de un usuario. |

## Bajos
| ID | Dónde | Qué pasa |
|---|---|---|
| BUG-12 | `deps.get_current_user` | Token inválido → 403 (debería ser 401); usuario inexistente → 404. |
| BUG-14 | `controllers/auth.py` | Busca "suspendida" pero el mensaje dice "suspendido": el login de una empresa suspendida responde 401 y no 400. |
| BUG-22 | `dashboard_service` | `mes_a=13` → IndexError → 500 con el texto interno; `mes_a=-1` se acepta y toma "Dic". |

## Riesgos detectados leyendo el código (sin test automático)
Dependen de Postgres o de infraestructura; no se pueden probar en SQLite.
1. **Día de caja y zona horaria.** `historial`, `recaudacion_hoy` y el resumen mensual usan `func.date(fecha)` sobre un `timestamptz` y `date.today()` del servidor. En un servidor en UTC, lo cobrado después de las 21:00 (Argentina) cae en el día siguiente y el cierre de caja no coincide con la jornada real.
2. **Sin idempotencia.** `POST /logistica/movimientos` no tiene clave de idempotencia: si el celular reintenta por mala señal, se duplican la entrega, la deuda y el stock de envases.
3. **Condiciones de carrera.** `saldo_dinero += x` y `stock_envases` se leen, modifican y guardan sin bloqueo de fila (`with_for_update`): dos entregas simultáneas al mismo cliente pierden una actualización.
4. **Envases recortados a 0.** El saldo de envases se fuerza a `max(0, …)`: devolver de más hace desaparecer el excedente y el saldo deja de ser recalculable desde los movimientos.
5. **Rate limit tras proxy.** El login usa `get_remote_address`; detrás de un proxy sin `X-Forwarded-For` configurado todos los usuarios comparten el límite de 5 intentos por minuto.
6. **Mensajes internos.** `registrar_entrega` y `dashboard` devuelven `str(e)` de excepciones internas al cliente; `/health` expone el texto de error de la base.
7. **Cloudinary.** `cloudinary_service` lee `os.getenv(...)`, pero pydantic-settings no carga el `.env` en `os.environ`: en local con `.env` la subida de logos falla. Además se borra el logo anterior **antes** de subir el nuevo (si falla la subida, se pierde el logo viejo).
8. **Integridad.** Las columnas `tenant_id` no tienen FK a `tenants`. Para un superadmin (`tenant_id=None`) los endpoints de admin consultan `tenant_id IS NULL` (ej. `/users` lista superadmins).
9. **Rendimiento.** El dashboard recorre todos los clientes en Python para sumar envases; el historial y las listas no tienen paginación ni índices compuestos por fecha.

## Orden sugerido para atacarlos
1. Seguridad y plata: BUG-23, BUG-02, BUG-03, BUG-18, BUG-17.
2. Funciones rotas: BUG-01, BUG-04, BUG-10.
3. Integridad contable: BUG-19, BUG-21, riesgos 1–3.
4. Validaciones y códigos HTTP: BUG-05, 06, 08, 09, 11, 13, 15, 16, 20, 24.
5. Detalles: BUG-12, 14, 22.

## Bloque B — auditoría de `services` del front contra el backend (2026-11-19)
Revisados `src/api/*.js` y los `api.*` sueltos en pantallas contra los controllers. Rutas, métodos, roles y campos coinciden.

| Hallazgo | Estado |
|---|---|
| `clientesService.getAll` pedía solo la primera página (`limit=100`): con más de 100 clientes quedaban afuera de la lista, de los recorridos y de la "Visita excepcional". | Corregido: recorre todas las páginas. |
| `SuperAdminDashboard` y `MetricasView` llamaban a `api` directamente (rutas duplicadas, query armada a mano). | Corregido: `tenantService` (listar, alta, editar, estado) y `dashboardService.getResumen(params)`. |
| Varios `catch` mostraban un texto fijo y descartaban el `detail` del backend (403 sin permiso, 404, 409 cliente con historial, 422), p. ej. el cobro, el alta de ruta/cliente/usuario y la contraseña ("Contraseña actual incorrecta" aunque fuera otro error). | Corregido: `notify.error(error, fallback)` en esas pantallas (la entrega ya lo hacía). |
| Entrega fuera de recorrido: el front no enviaba la marca. | Corregido: `visita_excepcional` en el payload; la pantalla muestra "Visita excepcional" y el historial la marca con una etiqueta y el conteo del mes. |
| Cobro: el monto se borraba aunque el guardado fallara. | Corregido: solo se limpia si salió bien. |
| Fallback `5491100000000` (Login y Portal). | Corregido: `src/lib/whatsapp.js` normaliza el número; sin WhatsApp cargado no se muestra el botón (Login) y el portal muestra un aviso en vez del enlace. |
| Colores azules por defecto en formularios (`ConfiguracionView`, `SuperAdminDashboard`). | Corregido: paleta de marca (el backend ya nace con ella). |
| UI: input pendiente de `UsuarioModal` (`field`), loaders propios de SuperAdmin/portal (`LoadingState`), spinner/colores sueltos de `TenantContext` y `MetricasView`. | Corregido. |
| Token inválido responde 403 (BUG-12): el interceptor del front solo cierra sesión con 401, así que un token vencido/corrupto deja la app mostrando errores. | **Abierto** (corregir el backend a 401 resuelve ambos lados). |
| Colores semánticos sueltos (`emerald-*`, `orange-*`, `amber-*`, `sky-*`) en Dashboard, Reparto, Precios, Resumen, Historial: necesitan tokens de color con variantes claras antes de reemplazarlos; no se tocaron para no cambiar el aspecto. | **Abierto**. |
| `GET /dashboard/resumen` mapea cualquier error a 500 con `str(e)` y el front lo muestra tal cual (riesgo 6). | **Abierto**. |
| ESLint (`npm run lint`) tiene errores previos en `AuthContext`, `TenantContext`, `PerfilEmpresa`; no son de este bloque. | **Abierto**. |

## Preparación para las próximas sesiones
**Bloque C — calendario operativo (hecho, requiere migración `e3a7c5d91b28`).** Modelo `Turno` (ruta + fecha + `hora_desde`/`hora_hasta` + nota) y `TurnoRepartidor` (1 a 3 repartidores por turno: exactamente un `conductor`, el resto `ayudante` de descarga). Una ruta tiene a lo sumo un turno por día; un repartidor no puede estar en dos turnos que se superponen el mismo día; solo repartidores activos de la empresa. Endpoints (`/logistica`): `GET /turnos?desde&hasta[&recorrido_id&repartidor_id]` (máx. 93 días; el repartidor ve solo los suyos), `POST /turnos`, `PUT/DELETE /turnos/{id}`, `POST /turnos/programar` (lote por rango de fechas y días de la semana, hasta 366 días, solo desde hoy; lo ocupado se omite y se informa) y `DELETE /turnos?recorrido_id&desde&hasta` (deshace una programación futura). Mutaciones solo admin. **Permisos:** quien tiene un turno HOY en una ruta (conductor o ayudante) la ve, puede registrar entregas/pagos de sus clientes y `Movimiento.repartidor_id` guarda quién operó. El chofer habitual (`Recorrido.repartidor_id`) sigue funcionando igual. Front: `/calendario` con pestañas Mensual/Semanal/Diario, filtros por ruta y repartidor, modal "Programar" (próximos 1/3/6/12 meses) y modal de turno; chofer habitual editable en la ruta. Pendiente: pantalla para deshacer una programación (el endpoint ya existe), avisar al repartidor de sus turnos, y verificar la UI en un navegador con datos reales.

**Bloque D — SuperAdmin: facturación, planes, datos fiscales y pagos.** Hoy `Tenant` solo tiene nombre, subdominio, WhatsApp, branding y `is_active`; no existen planes, suscripciones, datos fiscales ni pagos. Puntos a decidir: (1) modelo (`plan`, `suscripcion` con estado/vencimiento, datos fiscales de la empresa —razón social, CUIT, condición IVA—, registro de pagos/facturas); (2) política al vencer (suspender usando `is_active`, con aviso previo); (3) endpoints solo superadmin (el aislamiento por rol ya está cubierto por `test_permisos.py`); (4) validar CUIT (BUG-11 sigue abierto); (5) front: ampliar `SuperAdminDashboard` y `tenantService` (ya concentra las llamadas del superadmin). No integrar una pasarela de pago real sin definir antes el proveedor.
