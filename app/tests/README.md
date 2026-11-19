# Tests del backend

## Cómo correrlos
Desde `SaaS_Backend`:

```powershell
.\venv\Scripts\python.exe -m pytest app/tests -q
.\venv\Scripts\python.exe -m pytest app/tests -rx -q   # lista los bugs conocidos (xfail)
```

Los tests usan una base **SQLite temporal** (se fija en `conftest.py` antes de importar la app): nunca tocan
la base del `.env`. Cada test arranca con tablas vacías, sin rate limit y con claves foráneas activadas
(como Postgres). Los errores no controlados se ven como HTTP 500, igual que en producción.

## Correr contra PostgreSQL real (opcional)
Algunas garantías (bloqueo de fila en operaciones simultáneas) solo se pueden probar con PostgreSQL.
Con una base **descartable** cuyo nombre termine en `_test` (cada test borra y recrea las tablas):

```powershell
$env:TEST_DATABASE_URL = "postgresql://usuario:clave@localhost:5432/dripgestion_test"
.\venv\Scripts\python.exe -m pytest app/tests -q
```

## Convención de bugs
Un test marcado con `@bug("BUG-xx", ...)` es `xfail(strict=True)`: describe el comportamiento **correcto** y hoy
falla por un bug documentado en `AUDITORIA_BACKEND.md`. Cuando el bug se corrige, el test pasa y pytest lo marca como
fallo ("XPASS strict") para que se quite el decorador.

## Qué cubre cada archivo
| Archivo | Cubre |
|---|---|
| `conftest.py` | Base temporal, fábricas (empresas, usuarios, clientes, catálogo, rutas), login y el escenario `mundo` (2 empresas con admin, repartidor y datos). |
| `test_auth.py` | Login (ok, credenciales, empresa, inactivo, suspendida, form-data), rate limit 429, `/me`, token inválido, invalidación de sesiones (logout-all, cambio de contraseña), usuario/empresa desactivados con token vigente. |
| `test_permisos.py` | Matriz rol × endpoint (repartidor y cliente contra endpoints de admin), superadmin, y los accesos indebidos del rol CLIENTE y la escalada a superadmin. |
| `test_aislamiento_tenant.py` | Una empresa no ve/edita/borra clientes, catálogo, envases, rutas, movimientos, usuarios ni historial de otra; referencias cruzadas. |
| `test_usuarios.py` | Equipo: listado, alta, edición, desactivación, reseteo de contraseña, baja, cierre remoto de sesiones. |
| `test_clientes.py` | Alta con usuario de portal y PIN hasheado, duplicados, paginación, ficha con envases y valor de reposición, cambio de teléfono/PIN, baja, validaciones. |
| `test_productos.py` | Tipos de envase y productos: códigos normalizados, retornables, unidades, precios, activación, 404/422. |
| `test_logistica.py` | Recorridos (CRUD, asignación), visita excepcional (BUG-17: marca, historial/caja, aislamiento por empresa), detalle vacío (BUG-18), códigos 403/404 (BUG-20), entregas (saldo de dinero, envases retornables, devoluciones, atomicidad/rollback), permisos del repartidor, pagos manuales, historial, filtros y cierre de caja mensual. |
| `test_dashboard_portal.py` | KPIs, envases por tipo, métodos de pago, rendimiento por recorrido, comparativo de meses; portal del cliente (saldo, envases, últimos movimientos). |
| `test_tenants.py` | Info pública, alta de empresa + admin, suspensión/reactivación (cierra sesiones), branding, subida de logo (formato, tamaño, permisos, falla de Cloudinary mockeada). |
| `test_salud_y_seguridad.py` | `/`, `/health`, OpenAPI, CORS, superadmin inicial. |
| `test_zona_horaria.py` | Día de caja en hora local (corte a las 00:00 de Argentina), fin de mes y de año nocturnos, "hoy" del negocio, hora y fecha mostradas en historial y portal. |
| `test_idempotencia_concurrencia.py` | Reintentos con `Idempotency-Key` (entregas y pagos), conflicto entre clientes, aislamiento por empresa, peticiones simultáneas con la misma clave, bloqueo de fila (`FOR UPDATE`) y prueba de carga contable (solo PostgreSQL). |
| `test_api.py` | Tests previos del proyecto (humo, rutas protegidas, flujo de entrega). Se volvió hermético: antes dependía de que el producto ID 1 existiera en la base de desarrollo. |

## Limitaciones
- SQLite no tiene bloqueo de fila: la prueba de carga paralela se saltea ahí (`skipped`) y solo corre con
  `TEST_DATABASE_URL`. El bloqueo se verifica igualmente compilando la consulta para PostgreSQL.
- La suite todavía no se corrió contra un PostgreSQL real (no había uno disponible).
