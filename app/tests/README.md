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
| `test_logistica.py` | Recorridos (CRUD, asignación), entregas (saldo de dinero, envases retornables, devoluciones, atomicidad/rollback), permisos del repartidor, pagos manuales, historial, filtros y cierre de caja mensual. |
| `test_dashboard_portal.py` | KPIs, envases por tipo, métodos de pago, rendimiento por recorrido, comparativo de meses; portal del cliente (saldo, envases, últimos movimientos). |
| `test_tenants.py` | Info pública, alta de empresa + admin, suspensión/reactivación (cierra sesiones), branding, subida de logo (formato, tamaño, permisos, falla de Cloudinary mockeada). |
| `test_salud_y_seguridad.py` | `/`, `/health`, OpenAPI, CORS, superadmin inicial. |
| `test_api.py` | Tests previos del proyecto (humo, rutas protegidas, flujo de entrega). Se volvió hermético: antes dependía de que el producto ID 1 existiera en la base de desarrollo. |

## Limitaciones
- SQLite no reproduce el huso horario de `timestamptz` ni los bloqueos de fila de Postgres: esos riesgos están en
  `AUDITORIA_BACKEND.md` y quedan sin test automático.
- No hay tests de concurrencia ni de idempotencia (la API no las implementa todavía).
