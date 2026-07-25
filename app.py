import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import io

# ----------------- CONFIGURACIÓN PÁGINA -----------------
st.set_page_config(
    page_title="Gestión de Compras y Bodega - The Oranges",
    page_icon="🍊",
    layout="wide"
)

# ----------------- BASE DE DATOS: ESTRUCTURA Y MIGRACIONES -----------------
def inicializar_bd():
    conn = sqlite3.connect("compras_oranges.db")
    c = conn.cursor()
    
    # Tabla Ordenes de Compra Semanal
    c.execute("""
        CREATE TABLE IF NOT EXISTS ordenes_compra_semanal (
            id_orden INTEGER PRIMARY KEY AUTOINCREMENT,
            semana INTEGER,
            fecha_creacion TEXT,
            proveedor TEXT,
            estado TEXT DEFAULT 'ABIERTA'
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS detalle_frutas_compra (
            id_orden INTEGER,
            fruta TEXT,
            cantidad_estimada REAL,
            precio_estimado REAL,
            subtotal REAL
        )
    """)

    # Tabla Recepciones en Bodega con nuevos campos (costo_flete y canastillas_devueltas)
    c.execute("""
        CREATE TABLE IF NOT EXISTS ordenes_recepcion (
            id_orden INTEGER PRIMARY KEY AUTOINCREMENT,
            id_orden_compra_ref INTEGER,
            fecha_ingreso TEXT,
            proveedor TEXT,
            conductor_placa TEXT,
            documento_ref TEXT,
            canastillas_totales INTEGER,
            canastillas_devueltas INTEGER DEFAULT 0,
            peso_bruto_total REAL,
            tara_total REAL,
            peso_neto_total REAL,
            valor_total REAL,
            costo_flete REAL DEFAULT 0.0,
            estado_pago TEXT,
            monto_abonado REAL,
            saldo_pendiente REAL,
            observaciones TEXT,
            estado TEXT DEFAULT 'ACTIVO'
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS detalle_frutas_orden (
            id_orden INTEGER,
            fruta TEXT,
            kg_primera REAL, precio_primera REAL,
            kg_segunda REAL, precio_segunda REAL,
            kg_tercera REAL, precio_tercera REAL,
            kg_danado REAL, kilos_netos REAL, kilos_utiles REAL,
            precio_kg REAL, subtotal REAL
        )
    """)

    conn.commit()
    conn.close()

inicializar_bd()

# ----------------- INICIALIZAR SESSION STATE -----------------
if "ultima_orden_guardada" not in st.session_state:
    st.session_state.ultima_orden_guardada = None

# ----------------- FUNCIÓN EXPORTAR PDF -----------------
def exportar_soporte_bascula_pdf(orden_info, detalle_frutas):
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    p.setFont("Helvetica-Bold", 14)
    p.drawString(100, 750, "THE ORANGES - SOPORTE DE RECEPCIÓN Y BÁSCULA")
    p.setFont("Helvetica", 10)
    
    p.drawString(100, 730, f"N° Recepción: REC-{orden_info['id_orden']:04d}")
    p.drawString(100, 715, f"Fecha Ingreso: {orden_info['fecha']}")
    p.drawString(100, 700, f"Proveedor: {orden_info['proveedor']}")
    p.drawString(100, 685, f"Doc / Factura: {orden_info['documento']}")
    p.drawString(100, 670, f"Conductor / Placa: {orden_info['conductor']}")

    p.drawString(350, 730, f"Canastillas Recibidas: {orden_info['canastillas']}")
    p.drawString(350, 715, f"Canastillas Devueltas: {orden_info.get('canastillas_devueltas', 0)}")
    p.drawString(350, 700, f"Peso Bruto: {orden_info['bruto']:,.1f} Kg")
    p.drawString(350, 685, f"Tara Total: {orden_info['tara']:,.1f} Kg")
    p.drawString(350, 670, f"Peso Neto Báscula: {orden_info['neto']:,.1f} Kg")

    p.line(100, 655, 500, 655)
    
    y = 635
    p.setFont("Helvetica-Bold", 10)
    p.drawString(100, y, "Fruta")
    p.drawString(220, y, "Kg Útiles")
    p.drawString(300, y, "Dañado")
    p.drawString(380, y, "Precio/Kg")
    p.drawString(450, y, "Subtotal")
    p.line(100, y - 5, 500, y - 5)

    p.setFont("Helvetica", 9)
    y -= 20
    for item in detalle_frutas:
        p.drawString(100, y, str(item['fruta']))
        p.drawString(220, y, f"{item['utiles']:,.1f} Kg")
        p.drawString(300, y, f"{item['kg_danado']:,.1f} Kg")
        p.drawString(380, y, f"${item['precio']:,.2f}")
        p.drawString(450, y, f"${item['subtotal']:,.2f}")
        y -= 15

    p.line(100, y, 500, y)
    y -= 20
    p.setFont("Helvetica-Bold", 10)
    p.drawString(300, y, "Costo Flete:")
    p.drawString(450, y, f"${orden_info.get('costo_flete', 0):,.2f}")
    y -= 15
    p.drawString(300, y, "VALOR TOTAL:")
    p.drawString(450, y, f"${orden_info['valor_total']:,.2f}")
    y -= 15
    p.drawString(300, y, "Monto Abonado:")
    p.drawString(450, y, f"${orden_info['monto_abonado']:,.2f}")
    y -= 15
    p.drawString(300, y, "Saldo Pendiente:")
    p.drawString(450, y, f"${orden_info['saldo_pendiente']:,.2f}")

    p.showPage()
    p.save()
    buffer.seek(0)
    return buffer

# ----------------- NAVEGACIÓN Y ESTRUCTURA DE PESTAÑAS -----------------
st.title("🍊 Sistema Integrado de Compras, Bodega y Cadena de Suministro")

tab1, tab2, tab3 = st.tabs([
    "📝 Pestaña 1: Orden de Compra Semanal", 
    "⚖️ Pestaña 2: Recepción, Báscula y Liquidación", 
    "📈 Pestaña 3: Dashboard y Control Avanzado"
])

# ----------------- PESTAÑA 1: ORDEN DE COMPRA SEMANAL -----------------
with tab1:
    st.header("📝 Programación Semanal de Compras a Proveedores")
    
    col_oc1, col_oc2, col_oc3 = st.columns(3)
    with col_oc1:
        semana_oc = st.number_input("Número de Semana", min_value=1, max_value=53, value=12, key="oc_sem")
    with col_oc2:
        proveedor_oc = st.text_input("Nombre del Proveedor", placeholder="Ej: Finca La Naranjera", key="oc_prov")
    with col_oc3:
        fecha_oc = st.date_input("Fecha de Programación", datetime.now(), key="oc_fec")

    st.markdown("#### 🍇 Frutas Programadas")
    
    frutas_disponibles = ["Naranja Salustiana", "Naranja Valencia", "Mandarina", "Mango", "Maracuyá", "Lulo"]
    items_programados = []
    
    for i, fruta in enumerate(frutas_disponibles):
        col_f1, col_f2, col_f3 = st.columns([2, 2, 2])
        with col_f1:
            check_f = st.checkbox(f"Pedir {fruta}", key=f"oc_chk_{i}")
        if check_f:
            with col_f2:
                cant_est = st.number_input(f"Kg Estimados de {fruta}", min_value=0.0, step=500.0, key=f"oc_cant_{i}")
            with col_f3:
                precio_est = st.number_input(f"Precio Pactado/Kg ($) {fruta}", min_value=0.0, step=50.0, key=f"oc_pr_{i}")
            
            subt_est = cant_est * precio_est
            items_programados.append({
                "fruta": fruta, "cantidad": cant_est, "precio": precio_est, "subtotal": subt_est
            })

    if items_programados:
        tot_oc = sum(item['subtotal'] for item in items_programados)
        st.info(f"💵 **Total Estimado de la Orden:** $ {tot_oc:,.2f}")

    if st.button("💾 Guardar Orden de Compra Semanal", type="primary", key="btn_guardar_oc"):
        if proveedor_oc and items_programados:
            conn = sqlite3.connect("compras_oranges.db")
            c = conn.cursor()
            c.execute("INSERT INTO ordenes_compra_semanal (semana, fecha_creacion, proveedor) VALUES (?, ?, ?)",
                      (semana_oc, fecha_oc.strftime("%Y-%m-%d"), proveedor_oc))
            id_oc_creada = c.lastrowid

            for item in items_programados:
                c.execute("INSERT INTO detalle_frutas_compra (id_orden, fruta, cantidad_estimada, precio_estimado, subtotal) VALUES (?, ?, ?, ?, ?)",
                          (id_oc_creada, item['fruta'], item['cantidad'], item['precio'], item['subtotal']))
            conn.commit()
            conn.close()
            st.success(f"✅ Orden de Compra OC-{id_oc_creada:04d} registrada con éxito.")
        else:
            st.error("⚠️ Ingrese un proveedor y seleccione al menos una fruta con cantidad.")

# ----------------- PESTAÑA 2: RECEPCIÓN Y BÁSCULA -----------------
with tab2:
    st.header("⚖️ Recepción en Bodega, Control de Báscula y Liquidación")

    conn = sqlite3.connect("compras_oranges.db")
    df_oc_abiertas = pd.read_sql_query("SELECT id_orden, proveedor, semana FROM ordenes_compra_semanal WHERE estado = 'ABIERTA'", conn)
    conn.close()

    col_r1, col_r2 = st.columns(2)
    with col_r1:
        oc_opciones = ["Ingreso Directo (Sin OC previa)"] + [f"OC-{row['id_orden']:04d} - {row['proveedor']} (Semana {row['semana']})" for _, row in df_oc_abiertas.iterrows()]
        oc_seleccionada = st.selectbox("Asociar a Orden de Compra (Opcional)", oc_opciones, key="rec_oc_sel")
        
        id_oc_seleccionada = None
        proveedor_default = ""
        if oc_seleccionada != "Ingreso Directo (Sin OC previa)":
            id_oc_seleccionada = int(oc_seleccionada.split("-")[1].split(" ")[0])
            conn = sqlite3.connect("compras_oranges.db")
            c = conn.cursor()
            c.execute("SELECT proveedor FROM ordenes_compra_semanal WHERE id_orden = ?", (id_oc_seleccionada,))
            proveedor_default = c.fetchone()[0]
            conn.close()

    with col_r2:
        fecha_final_ingreso = st.datetime_input("Fecha y Hora de Entrada Báscula", datetime.now(), key="rec_fecha_ing")

    col_d1, col_d2, col_d3 = st.columns(3)
    with col_d1:
        proveedor_recep = st.text_input("Proveedor", value=proveedor_default, key="rec_prov")
    with col_d2:
        conductor_placa = st.text_input("Conductor / Placa Vehículo", placeholder="Ej: Pedro Pérez - ABC123", key="rec_cond")
    with col_d3:
        doc_ref = st.text_input("N° Documento Remisión / Factura", placeholder="Ej: REM-8842", key="rec_doc")

    st.markdown("---")
    st.markdown("#### 📦 Datos de Pesaje Global y Báscula")
    col_b1, col_b2, col_b3, col_b4 = st.columns(4)
    with col_b1:
        conteo_canastillas = st.number_input("Canastillas Recibidas", min_value=0, step=1, key="rec_canastillas")
    with col_b2:
        bruto_total = st.number_input("Peso Bruto Entrada (Kg)", min_value=0.0, step=10.0, key="rec_bruto")
    with col_b3:
        tara_por_canastilla = st.number_input("Tara Unit. Canastilla (Kg)", min_value=0.0, value=2.0, step=0.1, key="rec_tara_u")
        tara_total = (conteo_canastillas * tara_por_canastilla)
    with col_b4:
        neto_calculado_bascula = max(0.0, bruto_total - tara_total)
        st.metric("Peso Neto en Báscula (Kg)", f"{neto_calculado_bascula:,.1f} Kg")

    st.markdown("---")
    st.markdown("#### 🍊 Desglose por Calidades y Precios de Fruta")

    # Si viene de OC, cargar las frutas programadas
    frutas_para_recepcion = []
    if id_oc_seleccionada:
        conn = sqlite3.connect("compras_oranges.db")
        c = conn.cursor()
        c.execute("SELECT fruta, cantidad_estimada, precio_estimado FROM detalle_frutas_compra WHERE id_orden = ?", (id_oc_seleccionada,))
        frutas_para_recepcion = c.fetchall()
        conn.close()

    if not frutas_para_recepcion:
        frutas_sel = st.multiselect("Seleccionar Frutas a Ingresar", ["Naranja Salustiana", "Naranja Valencia", "Mandarina", "Mango", "Maracuyá", "Lulo"], default=["Naranja Salustiana"])
        frutas_para_recepcion = [(f, 0.0, 0.0) for f in frutas_sel]

    frutas_recepcion_capturadas = []
    valor_total_recepcion = 0.0

    for idx, (f_nom, f_cant, f_prom) in enumerate(frutas_para_recepcion):
        st.subheader(f"🔸 {f_nom}")
        usar_desglose = st.checkbox(f"Clasificar {f_nom} por Calidades (1ª, 2ª, 3ª)", value=False, key=f"chk_desglose_{idx}")

        if usar_desglose:
            c_c1, c_c2, c_c3 = st.columns(3)
            with c_c1:
                rk_1 = st.number_input(f"Kg Primera (1ª)", min_value=0.0, key=f"k1_{idx}")
                rp_1 = st.number_input(f"Precio 1ª ($/Kg)", min_value=0.0, key=f"p1_{idx}")
            with c_c2:
                rk_2 = st.number_input(f"Kg Segunda (2ª)", min_value=0.0, key=f"k2_{idx}")
                rp_2 = st.number_input(f"Precio 2ª ($/Kg)", min_value=0.0, key=f"p2_{idx}")
            with c_c3:
                rk_3 = st.number_input(f"Kg Tercera (3ª)", min_value=0.0, key=f"k3_{idx}")
                rp_3 = st.number_input(f"Precio 3ª ($/Kg)", min_value=0.0, key=f"p3_{idx}")

            col_d1, col_d2 = st.columns(2)
            with col_d1:
                kg_danado = st.number_input(f"⚠️ Fruta Dañada/Averiada (Kg) en {f_nom}", min_value=0.0, step=1.0, key=f"dan_desg_{idx}")
            with col_d2:
                descontar_danado = st.checkbox(f"¿Descontar fruta dañada del pago al proveedor?", value=True, key=f"desc_desg_{idx}")

            tot_k_f = rk_1 + rk_2 + rk_3 + kg_danado
            kg_utiles = rk_1 + rk_2 + rk_3
            subt_f = (rk_1 * rp_1) + (rk_2 * rp_2) + (rk_3 * rp_3)
            pr_prom_f = (subt_f / kg_utiles) if kg_utiles > 0 else 0.0

            st.info(f"📊 **Resumen {f_nom}:** Entrada Báscula: {tot_k_f:,.1f} Kg | Dañado: {kg_danado:,.1f} Kg | **Útiles: {kg_utiles:,.1f} Kg** | **Subtotal: $ {subt_f:,.2f}**")

            valor_total_recepcion += subt_f
            frutas_recepcion_capturadas.append({
                "fruta": f_nom, "kilos": tot_k_f, "kg_danado": kg_danado,
                "utiles": kg_utiles, "precio": pr_prom_f, "subtotal": subt_f,
                "kg_1": rk_1, "precio_1": rp_1, "kg_2": rk_2, "precio_2": rp_2,
                "kg_3": rk_3, "precio_3": rp_3
            })
        else:
            col_u1, col_u2 = st.columns(2)
            with col_u1:
                tot_k_f = st.number_input(f"Kg Reales Entregados de {f_nom}", min_value=0.0, value=float(f_cant), step=10.0, key=f"rk_u_{idx}")
            with col_u2:
                pr_u_f = st.number_input(f"Precio Pactado ($/Kg) para {f_nom}", min_value=0.0, value=float(f_prom), step=50.0, key=f"rp_u_{idx}")

            col_d1, col_d2 = st.columns(2)
            with col_d1:
                kg_danado = st.number_input(f"⚠️ Fruta Dañada/Averiada (Kg) en {f_nom}", min_value=0.0, max_value=float(tot_k_f) if tot_k_f > 0 else 0.0, step=1.0, key=f"dan_u_{idx}")
            with col_d2:
                descontar_danado = st.checkbox(f"¿Descontar fruta dañada del pago al proveedor?", value=True, key=f"desc_u_{idx}")

            kg_utiles = max(0.0, tot_k_f - kg_danado)
            subt_f = (kg_utiles if descontar_danado else tot_k_f) * pr_u_f

            st.info(f"📊 **Resumen {f_nom}:** Entrada Báscula: {tot_k_f:,.1f} Kg | Dañado: {kg_danado:,.1f} Kg | **Útiles: {kg_utiles:,.1f} Kg** | **Subtotal: $ {subt_f:,.2f}**")

            valor_total_recepcion += subt_f
            frutas_recepcion_capturadas.append({
                "fruta": f_nom, "kilos": tot_k_f, "kg_danado": kg_danado,
                "utiles": kg_utiles, "precio": pr_u_f, "subtotal": subt_f,
                "kg_1": 0.0, "precio_1": 0.0, "kg_2": 0.0, "precio_2": 0.0,
                "kg_3": 0.0, "precio_3": 0.0
            })
        st.markdown("---")

    # ----------------- LOGÍSTICA DE FLETES Y CANASTILLAS -----------------
    st.markdown("#### 🚚 Logística de Transporte y Canastillas")
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        costo_flete = st.number_input("💵 Costo de Flete / Transporte ($) [Opcional]", min_value=0.0, step=10000.0, key="rec_costo_flete")
        asumido_por_empresa = st.checkbox("¿El flete lo paga la empresa? (Prorratear en costo real del Kg)", value=True, key="rec_flete_empresa")
    with col_f2:
        canastillas_devueltas = st.number_input("🧺 Canastillas Devueltas al Proveedor (Entregadas en esta carga)", min_value=0, step=1, key="rec_can_dev")
        canastillas_saldo_neto = conteo_canastillas - canastillas_devueltas
        st.caption(f"📌 **Balance Canastillas de esta carga:** RECIBIDAS: {conteo_canastillas} | DEVUELTAS: {canastillas_devueltas} | **SALDO EN BODEGA: {canastillas_saldo_neto}**")

    st.markdown("---")

    # ----------------- GESTIÓN DE PAGOS Y SALDOS PENDIENTES -----------------
    st.markdown("#### 💰 Liquidación y Condición de Pago")
    col_p1, col_p2, col_p3 = st.columns(3)
    with col_p1:
        estado_pago = st.selectbox("Estado del Pago", ["Pendiente (Crédito)", "Pagado de Contado", "Abono Parcial"], key="rec_est_pago")
    
    monto_abonado = 0.0
    if estado_pago == "Pagado de Contado":
        monto_abonado = valor_total_recepcion
        with col_p2:
            st.number_input("Monto Abonado ($)", value=float(monto_abonado), disabled=True, key="rec_m_pagado")
    elif estado_pago == "Abono Parcial":
        with col_p2:
            monto_abonado = st.number_input("Monto Abonado ($)", min_value=0.0, max_value=float(valor_total_recepcion), step=50000.0, key="rec_m_abono")
    else:
        with col_p2:
            st.number_input("Monto Abonado ($)", value=0.0, disabled=True, key="rec_m_cero")

    saldo_pendiente = max(0.0, valor_total_recepcion - monto_abonado)
    with col_p3:
        st.markdown(f"**Saldo Pendiente por Pagar:**\n# $ {saldo_pendiente:,.2f}")

    # Cálculo de costo real prorrateado si aplica flete
    tot_utiles_lote = sum(item['utiles'] for item in frutas_recepcion_capturadas)
    costo_adicional_flete_kg = (costo_flete / tot_utiles_lote) if (asumido_por_empresa and tot_utiles_lote > 0) else 0.0
    if costo_adicional_flete_kg > 0:
        st.info(f"💡 **Impacto Logístico:** El flete añade un costo de **${costo_adicional_flete_kg:,.2f} / Kg** sobre la fruta útil ingresada.")

    obs_recepcion = st.text_area("Observaciones Generales de la Recepción (Bodega / Báscula)", key="rec_obs_txt")

    # ----------------- GUARDAR RECEPCIÓN EN BDF -----------------
    if st.button("💾 Registrar Entrada a Bodega y Liquidar", type="primary", use_container_width=True, key="btn_guardar_rec"):
        if proveedor_recep and valor_total_recepcion > 0:
            conn = sqlite3.connect("compras_oranges.db")
            c = conn.cursor()

            c.execute("""
                INSERT INTO ordenes_recepcion 
                (id_orden_compra_ref, fecha_ingreso, proveedor, conductor_placa, documento_ref, canastillas_totales, canastillas_devueltas, peso_bruto_total, tara_total, peso_neto_total, valor_total, costo_flete, estado_pago, monto_abonado, saldo_pendiente, observaciones, estado)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVO')
            """, (id_oc_seleccionada, fecha_final_ingreso.strftime("%Y-%m-%d %H:%M"), proveedor_recep, conductor_placa, doc_ref, conteo_canastillas, canastillas_devueltas, bruto_total, tara_total, neto_calculado_bascula, valor_total_recepcion, costo_flete, estado_pago, monto_abonado, saldo_pendiente, obs_recepcion))

            id_rec_creada = c.lastrowid

            for item in frutas_recepcion_capturadas:
                precio_final_con_flete = item['precio'] + costo_adicional_flete_kg
                c.execute("""
                    INSERT INTO detalle_frutas_orden
                    (id_orden, fruta, kg_primera, precio_primera, kg_segunda, precio_segunda, kg_tercera, precio_tercera, kg_danado, kilos_netos, kilos_utiles, precio_kg, subtotal)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (id_rec_creada, item['fruta'], item['kg_1'], item['precio_1'], item['kg_2'], item['precio_2'], item['kg_3'], item['precio_3'], item['kg_danado'], item['kilos'], item['utiles'], precio_final_con_flete, item['subtotal']))

            conn.commit()
            conn.close()

            orden_info_pdf = {
                "id_orden": id_rec_creada,
                "fecha": fecha_final_ingreso.strftime("%d/%m/%Y %I:%M %p"),
                "proveedor": proveedor_recep,
                "documento": doc_ref,
                "conductor": conductor_placa,
                "estado_pago": estado_pago,
                "canastillas": conteo_canastillas,
                "canastillas_devueltas": canastillas_devueltas,
                "costo_flete": costo_flete,
                "bruto": bruto_total,
                "tara": tara_total,
                "neto": neto_calculado_bascula,
                "valor_total": valor_total_recepcion,
                "monto_abonado": monto_abonado,
                "saldo_pendiente": saldo_pendiente
            }

            st.session_state.ultima_orden_guardada = (orden_info_pdf, frutas_recepcion_capturadas)
            st.success(f"✅ Recepción REC-{id_rec_creada:04d} registrada exitosamente.")
            st.rerun()
        else:
            st.error("⚠️ Complete los campos requeridos para procesar el ingreso a bodega.")

    # Descarga del soporte PDF e integración rápida de WhatsApp
    if st.session_state.ultima_orden_guardada:
        st.markdown("---")
        st.markdown("### 📄 Soportes y Notificación de Recepción")
        ord_info, lista_f = st.session_state.ultima_orden_guardada
        col_pdf_rec, col_wa_rec = st.columns(2)
        with col_pdf_rec:
            pdf_bytes_rec = exportar_soporte_bascula_pdf(ord_info, lista_f)
            st.download_button("📄 Descargar Soporte de Báscula (PDF)", data=pdf_bytes_rec, file_name=f"Soporte_Bascula_REC_{ord_info['id_orden']:04d}_{ord_info['proveedor']}.pdf", mime="application/pdf")
        with col_wa_rec:
            desglose_rec_wa = ""
            for item in lista_f:
                desglose_rec_wa += f"• *{item['fruta']}*: {item['utiles']:,.1f} Kg útiles = ${item['subtotal']:,.2f}\n"
                if item['kg_danado'] > 0:
                    desglose_rec_wa += f"   (⚠️ Dañado/Merma: {item['kg_danado']:,.1f} Kg)\n"

            flete_txt = f"\n*FLETE TRANSPORTE:* ${ord_info.get('costo_flete', 0):,.2f}" if ord_info.get('costo_flete', 0) > 0 else ""
            canast_txt = f"\n*Canastillas Recibidas/Devueltas:* {ord_info['canastillas']} / {ord_info.get('canastillas_devueltas', 0)}"

            texto_wa_rec = f"*🍊 THE ORANGES - SOPORTE RECEPCIÓN BODEGA*\n*REC-{ord_info['id_orden']:04d}* | {ord_info['proveedor']}\n*Doc/Factura:* {ord_info['documento']}{canast_txt}\n------------------------------------------------\n{desglose_rec_wa}------------------------------------------------{flete_txt}\n*VALOR TOTAL:* *${ord_info['valor_total']:,.2f}*\n*ABONADO:* ${ord_info['monto_abonado']:,.2f}\n*SALDO PENDIENTE:* *${ord_info['saldo_pendiente']:,.2f}*"
            st.text_area("Copia el soporte para WhatsApp:", value=texto_wa_rec, height=180)


# ----------------- PESTAÑA 3: DASHBOARD Y CONTROL AVANZADO -----------------
with tab3:
    st.header("📈 Dashboard de Compras, Bodega y Control de Costos")

    conn = sqlite3.connect("compras_oranges.db")
    
    # Cargar datos para métricas globales
    df_recepciones = pd.read_sql_query("SELECT * FROM ordenes_recepcion WHERE estado = 'ACTIVO'", conn)
    df_detalles = pd.read_sql_query("SELECT * FROM detalle_frutas_orden WHERE id_orden IN (SELECT id_orden FROM ordenes_recepcion WHERE estado = 'ACTIVO')", conn)
    
    if df_recepciones.empty:
        st.info("ℹ️ No hay registros activos en bodega para generar el reporte de métricas y costos.")
    else:
        # Métricas KPIs Clave
        tot_gastado = df_recepciones['valor_total'].sum()
        tot_fletes = df_recepciones['costo_flete'].sum() if 'costo_flete' in df_recepciones.columns else 0.0
        tot_abonado = df_recepciones['monto_abonado'].sum()
        tot_pendiente = df_recepciones['saldo_pendiente'].sum()
        tot_kilos_utiles = df_detalles['kilos_utiles'].sum()
        tot_kilos_danados = df_detalles['kg_danado'].sum()

        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("💰 Compras Netas", f"$ {tot_gastado:,.2f}")
        m2.metric("🚚 Fletes Totales", f"$ {tot_fletes:,.2f}")
        m3.metric("✅ Monto Pagado", f"$ {tot_abonado:,.2f}")
        m4.metric("🚨 Cuentas x Pagar", f"$ {tot_pendiente:,.2f}")
        m5.metric("🍇 Kilos Útiles", f"{tot_kilos_utiles:,.1f} Kg")

        st.markdown("---")

        col_d1, col_d2 = st.columns(2)

        with col_d1:
            st.subheader("📊 Volúmenes por Tipo de Fruta (Kg Útiles vs Dañados)")
            df_fruta_summary = df_detalles.groupby('fruta')[['kilos_utiles', 'kg_danado']].sum().reset_index()
            st.dataframe(df_fruta_summary.style.format({
                'kilos_utiles': '{:,.1f} Kg',
                'kg_danado': '{:,.1f} Kg'
            }), use_container_width=True)

        with col_d2:
            st.subheader("💵 Inversión y Costo Promedio por Fruta")
            df_costo_summary = df_detalles.groupby('fruta').agg(
                Inversion_Total=('subtotal', 'sum'),
                Kilos_Totales=('kilos_utiles', 'sum')
            ).reset_index()
            df_costo_summary['Costo_Promedio_Kg'] = df_costo_summary.apply(
                lambda r: (r['Inversion_Total'] / r['Kilos_Totales']) if r['Kilos_Totales'] > 0 else 0, axis=1
            )
            st.dataframe(df_costo_summary.style.format({
                'Inversion_Total': '$ {:,.2f}',
                'Kilos_Totales': '{:,.1f} Kg',
                'Costo_Promedio_Kg': '$ {:,.2f}/Kg'
            }), use_container_width=True)

        st.markdown("---")

        # ----------------- SUB-PESTAÑAS DE MONITOREO Y EDICIÓN -----------------
        sub_t1, sub_t2, sub_t3, sub_t4 = st.tabs([
            "🔍 Buscador / Histórico & Edición", 
            "🧺 Control Canastillas x Proveedor", 
            "📈 Histórico Precios x Proveedor", 
            "📋 Cuentas por Pagar"
        ])

        # --- SUB-PESTAÑA 1: BUSCADOR & ANULACIÓN / EDICIÓN ---
        with sub_t1:
            st.subheader("🔍 Filtrar, Consultar y Gestor de Recepciones")
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                prov_filtro = st.multiselect("Filtrar por Proveedor", options=df_recepciones['proveedor'].unique())
            with col_b2:
                buscar_doc = st.text_input("Buscar por ID Orden (REC) o N° Factura/Documento")

            df_filtrado = df_recepciones.copy()
            if prov_filtro:
                df_filtrado = df_filtrado[df_filtrado['proveedor'].isin(prov_filtro)]
            if buscar_doc:
                df_filtrado = df_filtrado[
                    df_filtrado['documento_ref'].str.contains(buscar_doc, case=False, na=False) | 
                    df_filtrado['id_orden'].astype(str).str.contains(buscar_doc)
                ]

            st.dataframe(df_filtrado[['id_orden', 'fecha_ingreso', 'proveedor', 'documento_ref', 'canastillas_totales', 'canastillas_devueltas', 'peso_neto_total', 'costo_flete', 'valor_total', 'saldo_pendiente']], use_container_width=True)

            st.markdown("##### ✏️ Editar Observaciones o Anular Registro de Recepción")
            col_e1, col_e2 = st.columns(2)
            with col_e1:
                id_rec_edit = st.selectbox("Seleccione N° Recepción (REC)", options=df_filtrado['id_orden'].unique())
            
            if id_rec_edit:
                rec_sel = df_filtrado[df_filtrado['id_orden'] == id_rec_edit].iloc[0]
                nueva_obs = st.text_area("Modificar Observación", value=rec_sel['observaciones'])
                
                col_btn_e1, col_btn_e2 = st.columns(2)
                with col_btn_e1:
                    if st.button("💾 Actualizar Observación", key="btn_mod_obs"):
                        c = conn.cursor()
                        c.execute("UPDATE ordenes_recepcion SET observaciones = ? WHERE id_orden = ?", (nueva_obs, id_rec_edit))
                        conn.commit()
                        st.success("Observación actualizada.")
                        st.rerun()
                with col_btn_e2:
                    if st.button("🚨 Anular Recepción (Error de Digitación)", type="primary", key="btn_anular_rec"):
                        c = conn.cursor()
                        c.execute("UPDATE ordenes_recepcion SET estado = 'ANULADO' WHERE id_orden = ?", (id_rec_edit,))
                        conn.commit()
                        st.warning(f"Recepción REC-{id_rec_edit:04d} Anulada correctamente.")
                        st.rerun()

        # --- SUB-PESTAÑA 2: CONTROL DE CANASTILLAS ---
        with sub_t2:
            st.subheader("🧺 Estado Cuenta de Canastillas por Proveedor")
            
            df_canastillas = df_recepciones.groupby('proveedor').agg(
                Canastillas_Ingresadas=('canastillas_totales', 'sum'),
                Canastillas_Devueltas=('canastillas_devueltas', 'sum')
            ).reset_index()
            
            df_canastillas['Saldo_Pendiente_Planta'] = df_canastillas['Canastillas_Ingresadas'] - df_canastillas['Canastillas_Devueltas']

            st.dataframe(df_canastillas.style.format({
                'Canastillas_Ingresadas': '{:,.0f}',
                'Canastillas_Devueltas': '{:,.0f}',
                'Saldo_Pendiente_Planta': '{:,.0f}'
            }), use_container_width=True)
            st.caption("💡 *Nota: 'Saldo Pendiente Planta' representa el número de canastillas del proveedor que aún se conservan en nuestras instalaciones.*")

        # --- SUB-PESTAÑA 3: HISTÓRICO DE PRECIOS ---
        with sub_t3:
            st.subheader("📈 Evolución y Variación de Precios por Kilo Comprado")
            
            df_precios_hist = df_detalles.merge(df_recepciones[['id_orden', 'fecha_ingreso', 'proveedor']], on='id_orden')
            
            fruta_sel_graf = st.selectbox("Seleccione Fruta para Analizar", options=df_precios_hist['fruta'].unique())
            df_p_fruta = df_precios_hist[df_precios_hist['fruta'] == fruta_sel_graf]

            if not df_p_fruta.empty:
                st.line_chart(data=df_p_fruta, x='fecha_ingreso', y='precio_kg', color='proveedor')
                
                st.markdown("##### 📋 Registro Detallado de Precios Pagados")
                st.dataframe(df_p_fruta[['fecha_ingreso', 'proveedor', 'fruta', 'kilos_utiles', 'precio_kg', 'subtotal']].style.format({
                    'kilos_utiles': '{:,.1f} Kg',
                    'precio_kg': '$ {:,.2f}',
                    'subtotal': '$ {:,.2f}'
                }), use_container_width=True)

        # --- SUB-PESTAÑA 4: CUENTAS POR PAGAR ---
        with sub_t4:
            st.subheader("📋 Cuentas por Pagar a Proveedores")
            df_cxp = df_recepciones[df_recepciones['saldo_pendiente'] > 0][['id_orden', 'fecha_ingreso', 'proveedor', 'documento_ref', 'valor_total', 'monto_abonado', 'saldo_pendiente', 'estado_pago']]
            
            if df_cxp.empty:
                st.success("🎉 ¡Excelente! No existen saldos pendientes por pagar a proveedores.")
            else:
                st.dataframe(df_cxp.style.format({
                    'valor_total': '$ {:,.2f}',
                    'monto_abonado': '$ {:,.2f}',
                    'saldo_pendiente': '$ {:,.2f}'
                }), use_container_width=True)

    conn.close()