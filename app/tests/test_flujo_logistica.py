def test_flujo_completo_entrega_y_saldo(client, normal_user_token_headers, db):
    
    cliente_data = {
        "nombre_negocio": "Kiosco Test",
        "direccion": "Calle Falsa 123",
        "telefono": "123456789"
    }
    res_cliente = client.post("/api/v1/clientes", headers=normal_user_token_headers, json=cliente_data)
    assert res_cliente.status_code == 200
    cliente_id = res_cliente.json()["id"]

    movimiento_data = {
        "cliente_id": cliente_id,
        "detalles": {"1": {"entregado": 2, "devuelto": 0}}, 
        "monto_total": 5000,
        "monto_cobrado": 2000,
        "metodo_pago": "efectivo",
        "observacion": "Prueba de integración"
    }
    
    res_mov = client.post("/api/v1/logistica/movimientos", headers=normal_user_token_headers, json=movimiento_data)
    assert res_mov.status_code == 200

    res_verify = client.get(f"/api/v1/clientes/{cliente_id}", headers=normal_user_token_headers)
    assert res_verify.status_code == 200
    assert res_verify.json()["saldo_dinero"] == 3000