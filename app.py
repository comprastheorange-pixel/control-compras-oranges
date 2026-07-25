import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
import io

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

st.set_page_config(page_title="The Oranges - Control de Compras y Bodega", layout="wide")
st.title("🍊 Sistema de Control de Compras, Bodega y Logística")

# ----------------- BASE DE DATOS Y AUTO-MIGRACIÓN -----------------

def init_db():
    conn = sqlite3.connect("compras_oranges.db")
    c = conn.cursor()
    
    # 1. Tabla Ordenes de Compra Semanal
    c.execute("""
    CREATE TABLE IF NOT EXISTS ordenes_compra_semanal (
        id_orden_compra INTEGER PRIMARY KEY AUTOINCREMENT,
        id_semana TEXT NOT NULL,
        proveedor TEXT NOT NULL,
        fecha_inicio DATE NOT NULL,
        fecha_fin DATE NOT NULL,
        observaciones TEXT
    )
    """)

    # 2. Detalle Orden de Compra
    c.execute("""
    CREATE TABLE IF NOT EXISTS detalle_orden_compra (
        id_detalle_oc INTEGER PRIMARY KEY AUTOINCREMENT,
        id_orden_compra INTEGER NOT NULL,
        fruta TEXT NOT NULL,
        modo_precio TEXT NOT NULL,
        kg_primera REAL DEFAULT 0,
        precio_primera REAL DEFAULT 0,
        kg_segunda REAL DEFAULT 0,
        precio_segunda REAL DEFAULT 0,
        kg_tercera REAL DEFAULT 0,
        precio_tercera REAL DEFAULT 0,
        cantidad_total REAL NOT NULL,
        precio_promedio REAL NOT NULL,
        subtotal_pactado REAL NOT NULL,
        FOREIGN KEY (id_orden_compra) REFERENCES ordenes_compra_semanal (id_orden_compra)
    )
    """)

    # 3. Tabla Recepciones en Bodega
    c.execute("""
    CREATE TABLE IF NOT EXISTS ordenes_recepcion (
        id_orden INTEGER PRIMARY KEY AUTOINCREMENT,
        id_orden_compra_ref INTEGER,
        fecha_ingreso DATETIME NOT NULL,
        proveedor TEXT NOT NULL,
        conductor_placa TEXT,
        documento_ref TEXT,
        canastillas_totales INTEGER DEFAULT 0,
        canastillas_devueltas INTEGER DEFAULT 0,
        peso_bruto_total REAL DEFAULT 0,
        tara_total REAL DEFAULT 0,
        peso_neto_total REAL DEFAULT 0,
        costo_flete REAL DEFAULT 0,
        valor_total REAL NOT NULL,
        estado_pago TEXT NOT NULL,
        monto_abonado REAL DEFAULT 0,
        saldo_pendiente REAL DEFAULT 0,
        observaciones TEXT,
        FOREIGN KEY (id_orden_compra_ref) REFERENCES ordenes_compra_semanal (id_orden_compra)
    )
    """)

    # Migraciones automáticas
    c.execute("PRAGMA table_info(ordenes_recepcion)")
    cols_rec = [column[1] for column in c.fetchall()]
    if "costo_flete" not in cols_rec:
        c.execute("ALTER TABLE ordenes_recepcion ADD COLUMN costo_flete REAL DEFAULT 0")
    if "canastillas_devueltas" not in cols_rec:
        c.execute("ALTER TABLE ordenes_recepcion ADD COLUMN canastillas_devueltas INTEGER DEFAULT 0")

    # 4. Detalle Frutas en Recepción (almacena el pesaje por canastilla)
    c.execute("""
    CREATE TABLE IF NOT EXISTS detalle_frutas_orden (
        id_detalle INTEGER PRIMARY KEY AUTOINCREMENT,
        id_orden INTEGER NOT NULL,
        fruta TEXT NOT NULL,
        num_canastillas INTEGER DEFAULT 0,
        tara_unit_canastilla REAL DEFAULT 0,
        peso_bruto REAL DEFAULT 0,
        tara_calculada REAL DEFAULT 0,
        kg_danado REAL DEFAULT 0,
        kilos_netos REAL NOT NULL,
        kilos_utiles REAL NOT NULL,
        precio_kg REAL NOT NULL,
        subtotal REAL NOT NULL,
        FOREIGN KEY (id_orden) REFERENCES ordenes_recepcion (id_orden)
    )
    """)

    # Migraciones para la tabla detalle si venía de versión previa
    c.execute("PRAGMA table_info(detalle_frutas_orden)")
    cols_det = [column[1] for column in c.fetchall()]
    if "num_canastillas" not in cols_det:
        c.execute("ALTER TABLE detalle_frutas_orden ADD COLUMN num_canastillas INTEGER DEFAULT 0")
    if "tara_unit_canastilla" not in cols_det:
        c.execute("ALTER TABLE detalle_frutas_orden ADD COLUMN tara_unit_canastilla REAL DEFAULT 0")
    if "peso_bruto" not in cols_det:
        c.execute("ALTER TABLE detalle_frutas_orden ADD COLUMN peso_bruto REAL DEFAULT 0")
    if "tara_calculada" not in cols_det:
        c.execute("ALTER TABLE detalle_frutas_orden ADD COLUMN tara_calculada REAL DEFAULT 0")

    # 5. Tabla Control/Kardex de Canastillas
    c.execute("""
    CREATE TABLE IF NOT EXISTS control_canastillas (
        id_movimiento INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha DATETIME NOT NULL,
        proveedor TEXT NOT NULL,
        tipo_movimiento TEXT NOT NULL,
        cantidad INTEGER NOT NULL,
        observaciones TEXT
    )
    """)

    conn.commit()
    conn.close()

init_db()

LISTA_FRUTAS = [
    "CHULUPA", "FRESA", "GUANABANA", "GUAYABA", "LIMON", 
    "LULO", "MANGO", "MARACUYA", "MORA", "NARANJA", 
    "PIÑA", "TOMATE ARBOL", "UVA", "OTRA (Escribir nueva...)"
]

# ----------------- FUNCIONES DE PDF -----------------

def generar_pdf_recepcion(id_orden):
    conn = sqlite3.connect("compras_oranges.db")
    df_enc = pd.read_sql_query("SELECT * FROM ordenes_recepcion WHERE id_orden = ?", conn, params=(id_orden,))
    df_det = pd.read_sql_query("SELECT * FROM detalle_frutas_orden WHERE id_orden = ?", conn, params=(id_orden,))
    conn.close()

    if df_enc.empty:
        return None

    enc = df_enc.iloc[0]
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    story = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=16, textColor=colors.HexColor('#D35400'), alignment=1)
    subtitle_style = ParagraphStyle('SubTitleStyle', parent=styles['Normal'], fontSize=10, textColor=colors.gray, alignment=1)
    label_style = ParagraphStyle('LabelStyle', parent=styles['Normal'], fontSize=9, fontName='Helvetica-Bold')
    value_style = ParagraphStyle('ValueStyle', parent=styles['Normal'], fontSize=9)
    table_hdr_style = ParagraphStyle('TableHdrStyle', parent=styles['Normal'], fontSize=8, fontName='Helvetica-Bold', textColor=colors.white)

    story.append(Paragraph("<b>THE ORANGES - COMPROBANTE DE BODEGA</b>", title_style))
    story.append(Paragraph("Sistema de Control de Recepción y Liquidación de Materia Prima", subtitle_style))
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#D35400'), spaceAfter=10))

    data_info = [
        [Paragraph("N° Recepción:", label_style), Paragraph(f"<b>#{enc['id_orden']}</b>", value_style), Paragraph("Fecha Ingreso:", label_style), Paragraph(str(enc['fecha_ingreso']), value_style)],
        [Paragraph("Proveedor:", label_style), Paragraph(str(enc['proveedor']), value_style), Paragraph("Documento Ref / Factura:", label_style), Paragraph(str(enc['documento_ref']), value_style)],
        [Paragraph("Conductor / Placa:", label_style), Paragraph(str(enc['conductor_placa']), value_style), Paragraph("Estado Pago:", label_style), Paragraph(str(enc['estado_pago']), value_style)],
        [Paragraph("Canastillas Recibidas:", label_style), Paragraph(str(enc['canastillas_totales']), value_style), Paragraph("Canastillas Devueltas:", label_style), Paragraph(str(enc['canastillas_devueltas']), value_style)]
    ]
    
    t_info = Table(data_info, colWidths=[110, 160, 120, 150])
    t_info.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#FDF2E9')),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#E5E7E9')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t_info)
    story.append(Spacer(1, 12))

    headers = ["Fruta", "Canastillas", "P. Bruto", "Tara (Kg)", "Kg Útiles", "Precio $/Kg", "Subtotal ($)"]
    data_prod = [[Paragraph(h, table_hdr_style) for h in headers]]

    for _, row in df_det.iterrows():
        data_prod.append([
            Paragraph(str(row['fruta']), value_style),
            Paragraph(str(row.get('num_canastillas', 0)), value_style),
            Paragraph(f"{row.get('peso_bruto', 0):,.2f}", value_style),
            Paragraph(f"{row.get('tara_calculada', 0):,.2f}", value_style),
            Paragraph(f"{row['kilos_utiles']:,.2f}", value_style),
            Paragraph(f"${row['precio_kg']:,.2f}", value_style),
            Paragraph(f"${row['subtotal']:,.2f}", value_style)
        ])

    t_prod = Table(data_prod, colWidths=[100, 60, 65, 65, 75, 80, 95])
    t_prod.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#D35400')),
        ('ALIGN', (1,1), (-1,-1), 'RIGHT'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#BDC3C7')),
        ('PADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t_prod)
    story.append(Spacer(1, 10))

    data_resumen = [
        [Paragraph("Costo Flete / Transporte:", label_style), Paragraph(f"${enc['costo_flete']:,.2f}", value_style)],
        [Paragraph("Valor Total Fruta:", label_style), Paragraph(f"<b>${enc['valor_total']:,.2f}</b>", value_style)],
        [Paragraph("Monto Abonado:", label_style), Paragraph(f"${enc['monto_abonado']:,.2f}", value_style)],
        [Paragraph("Saldo Pendiente:", label_style), Paragraph(f"<b>${enc['saldo_pendiente']:,.2f}</b>", value_style)]
    ]
    
    t_res = Table(data_resumen, colWidths=[200, 150])
    t_res.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'RIGHT'),
        ('LINEABOVE', (0,0), (-1,0), 1, colors.HexColor('#D35400')),
        ('PADDING', (0,0), (-1,-1), 3),
    ]))
    story.append(t_res)

    if enc['observaciones']:
        story.append(Spacer(1, 10))
        story.append(Paragraph(f"<b>Observaciones:</b> {enc['observaciones']}", value_style))

    doc.build(story)
    buffer.seek(0)
    return buffer

# ----------------- ESTRUCTURA DE PESTAÑAS -----------------

tab1, tab2, tab3, tab4 = st.tabs([
    "📋 Planeación Semanal (OC)", 
    "🚛 Recepción y Báscula", 
    "📈 Dashboard y Finanzas",
    "🚚 Logística, Canastillas y Precios"
])

# ==============================================================================
# PESTAÑA 1: PLANEACIÓN SEMANAL (ÓRDENES DE COMPRA)
# ==============================================================================
with tab1:
    st.header("📋 Emisión de Órdenes de Compra Semanales")
    
    with st.form("form_oc_semanal"):
        col_oc1, col_oc2, col_oc3 = st.columns(3)
        with col_oc1:
            id_semana = st.text_input("Identificador de Semana (Ej: Semana 30 - Julio)", key="oc_semana")
            proveedor_oc = st.text_input("Nombre del Proveedor", key="oc_prov")
        with col_oc2:
            fecha_inicio = st.date_input("Fecha Inicio", key="oc_f_ini")
            fecha_fin = st.date_input("Fecha Fin", key="oc_f_fin")
        with col_oc3:
            obs_oc = st.text_area("Observaciones de la OC", key="oc_obs")

        st.subheader("Detalle de Frutas Acordadas")
        num_frutas_oc = st.number_input("Número de frutas a registrar en esta OC", min_value=1, max_value=10, value=1)
        
        detalles_oc = []
        for i in range(int(num_frutas_oc)):
            st.markdown(f"**Fruta #{i+1}**")
            cf1, cf2, cf3, cf4 = st.columns([2, 2, 2, 2])
            with cf1:
                f_sel = st.selectbox(f"Fruta #{i+1}", LISTA_FRUTAS, key=f"oc_f_{i}")
                if f_sel == "OTRA (Escribir nueva...)":
                    f_sel = st.text_input(f"Nombre de la nueva fruta #{i+1}", key=f"oc_f_custom_{i}")
            with cf2:
                modo_p = st.selectbox(f"Clasificación de Precio #{i+1}", ["Precio Único", "Por Calidades (1ra, 2da, 3ra)"], key=f"oc_m_{i}")
            
            kg_1, p_1, kg_2, p_2, kg_3, p_3 = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
            
            if modo_p == "Precio Único":
                with cf3:
                    kg_1 = st.number_input(f"Kilos Pactados #{i+1}", min_value=0.0, step=10.0, key=f"oc_kg1_{i}")
                with cf4:
                    p_1 = st.number_input(f"Precio por Kilo #{i+1}", min_value=0.0, step=50.0, key=f"oc_p1_{i}")
                cant_tot = kg_1
                subtot = kg_1 * p_1
                p_prom = p_1 if kg_1 > 0 else 0
            else:
                c_q1, c_q2, c_q3 = st.columns(3)
                with c_q1:
                    kg_1 = st.number_input(f"Kg 1ra #{i+1}", min_value=0.0, key=f"oc_kg1_q_{i}")
                    p_1 = st.number_input(f"Precio 1ra #{i+1}", min_value=0.0, key=f"oc_p1_q_{i}")
                with c_q2:
                    kg_2 = st.number_input(f"Kg 2da #{i+1}", min_value=0.0, key=f"oc_kg2_q_{i}")
                    p_2 = st.number_input(f"Precio 2da #{i+1}", min_value=0.0, key=f"oc_p2_q_{i}")
                with c_q3:
                    kg_3 = st.number_input(f"Kg 3ra #{i+1}", min_value=0.0, key=f"oc_kg3_q_{i}")
                    p_3 = st.number_input(f"Precio 3ra #{i+1}", min_value=0.0, key=f"oc_p3_q_{i}")
                
                cant_tot = kg_1 + kg_2 + kg_3
                subtot = (kg_1 * p_1) + (kg_2 * p_2) + (kg_3 * p_3)
                p_prom = subtot / cant_tot if cant_tot > 0 else 0

            detalles_oc.append({
                "fruta": f_sel, "modo_precio": modo_p, 
                "kg_1": kg_1, "p_1": p_1, "kg_2": kg_2, "p_2": p_2, "kg_3": kg_3, "p_3": p_3,
                "cantidad_total": cant_tot, "precio_promedio": p_prom, "subtotal_pactado": subtot
            })

        btn_guardar_oc = st.form_submit_button("💾 Guardar Orden de Compra")

    if btn_guardar_oc:
        if proveedor_oc and id_semana:
            conn = sqlite3.connect("compras_oranges.db")
            c = conn.cursor()
            c.execute("""
                INSERT INTO ordenes_compra_semanal (id_semana, proveedor, fecha_inicio, fecha_fin, observaciones)
                VALUES (?, ?, ?, ?, ?)
            """, (id_semana, proveedor_oc, fecha_inicio, fecha_fin, obs_oc))
            id_oc_creada = c.lastrowid

            for d in detalles_oc:
                c.execute("""
                    INSERT INTO detalle_orden_compra 
                    (id_orden_compra, fruta, modo_precio, kg_primera, precio_primera, kg_segunda, precio_segunda, kg_tercera, precio_tercera, cantidad_total, precio_promedio, subtotal_pactado)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (id_oc_creada, d["fruta"], d["modo_precio"], d["kg_1"], d["p_1"], d["kg_2"], d["p_2"], d["kg_3"], d["p_3"], d["cantidad_total"], d["precio_promedio"], d["subtotal_pactado"]))

            conn.commit()
            conn.close()
            st.success(f"✅ Orden de Compra #{id_oc_creada} guardada con éxito.")
        else:
            st.error("⚠️ Por favor completa el proveedor y el identificador de la semana.")

# ==============================================================================
# PESTAÑA 2: RECEPCIÓN Y BÁSCULA (CON PESAJE POR CANASTILLAS RESTAURADO)
# ==============================================================================
with tab2:
    st.header("🚛 Recepción de Materia Prima en Báscula")

    conn = sqlite3.connect("compras_oranges.db")
    df_ocs_activas = pd.read_sql_query("SELECT id_orden_compra, id_semana, proveedor FROM ordenes_compra_semanal ORDER BY id_orden_compra DESC", conn)
    conn.close()

    oc_opciones = ["Sin Orden de Compra (Directo)"] + [f"OC #{row['id_orden_compra']} - {row['proveedor']} ({row['id_semana']})" for _, row in df_ocs_activas.iterrows()]
    oc_seleccionada = st.selectbox("Asociar a Orden de Compra Semanal (Opcional):", oc_opciones)

    id_oc_ref = None
    prov_defecto = ""
    if oc_seleccionada != "Sin Orden de Compra (Directo)":
        id_oc_ref = int(oc_seleccionada.split("#")[1].split(" ")[0])
        prov_defecto = oc_seleccionada.split("- ")[1].split(" (")[0]

    with st.form("form_recepcion_bascula"):
        col_r1, col_r2, col_r3 = st.columns(3)
        with col_r1:
            prov_rec = st.text_input("Proveedor", value=prov_defecto, key="rec_prov")
            conductor_placa = st.text_input("Conductor / Placa del Vehículo", key="rec_cond")
        with col_r2:
            doc_ref = st.text_input("Documento de Referencia / Factura / DS", key="rec_doc")
            canastillas_dev = st.number_input("Canastillas Devueltas al Conductor", min_value=0, step=1, key="rec_can_dev")
        with col_r3:
            costo_flete_ingresado = st.number_input("Costo del Flete / Transporte ($)", min_value=0.0, step=5000.0, key="rec_flete")
            estado_pago = st.selectbox("Estado del Pago", ["Pendiente", "Abonado", "Pagado Totalidad"])
            monto_abonado = st.number_input("Monto Abonado en Recepción ($)", min_value=0.0, step=10000.0)

        st.markdown("---")
        st.subheader("⚖️ Pesaje y Clasificación por Canastillas y Fruta")

        num_frutas_rec = st.number_input("Cantidad de frutas/lotes a pesarle al proveedor", min_value=1, max_value=10, value=1)
        
        detalles_recepcion = []
        peso_bruto_acum = 0.0
        tara_acum = 0.0
        canastillas_acum = 0
        valor_total_fruta = 0.0

        for i in range(int(num_frutas_rec)):
            st.markdown(f"#### **Lote / Fruta #{i+1}**")
            col_f1, col_f2 = st.columns([2, 2])
            with col_f1:
                fruta_r = st.selectbox(f"Seleccionar Fruta #{i+1}", LISTA_FRUTAS, key=f"rf_f_{i}")
                if fruta_r == "OTRA (Escribir nueva...)":
                    fruta_r = st.text_input(f"Nombre de fruta #{i+1}", key=f"rf_custom_{i}")
            
            st.markdown("**Pesaje en Báscula y Cálculo de Tara por Canastilla:**")
            cp1, cp2, cp3, cp4, cp5 = st.columns(5)
            with cp1:
                n_canastillas = st.number_input(f"N° Canastillas #{i+1}", min_value=0, step=1, value=1, key=f"rf_ncan_{i}")
            with cp2:
                tara_unit = st.number_input(f"Tara / Canastilla (Kg) #{i+1}", min_value=0.0, value=2.0, step=0.1, key=f"rf_tunit_{i}")
            with cp3:
                p_bruto = st.number_input(f"Peso Bruto Total (Kg) #{i+1}", min_value=0.0, step=1.0, key=f"rf_bruto_{i}")
            with cp4:
                kg_danado = st.number_input(f"Fruta Dañada/Merma (Kg) #{i+1}", min_value=0.0, step=0.5, key=f"rf_dan_{i}")
            with cp5:
                p_kg_acordado = st.number_input(f"Precio Compra $/Kg #{i+1}", min_value=0.0, step=50.0, key=f"rf_pkg_{i}")

            # Cálculos automáticos por canastilla
            tara_calculada = n_canastillas * tara_unit
            kg_netos = max(0.0, p_bruto - tara_calculada)
            kg_utiles = max(0.0, kg_netos - kg_danado)
            subtot_f = kg_utiles * p_kg_acordado

            peso_bruto_acum += p_bruto
            tara_acum += tara_calculada
            canastillas_acum += n_canastillas
            valor_total_fruta += subtot_f

            st.info(
                f"📊 **Resumen Lote #{i+1}:** Canastillas: {n_canastillas} Uds | Tara Total: {tara_calculada:,.2f} Kg | "
                f"Kilos Netos: {kg_netos:,.2f} Kg | Kilos Útiles: **{kg_utiles:,.2f} Kg** | Subtotal: **${subtot_f:,.2f}**"
            )

            detalles_recepcion.append({
                "fruta": fruta_r, 
                "num_canastillas": n_canastillas,
                "tara_unit_canastilla": tara_unit,
                "p_bruto": p_bruto, 
                "tara_calculada": tara_calculada,
                "kg_danado": kg_danado, 
                "kg_netos": kg_netos, 
                "kg_utiles": kg_utiles,
                "precio_kg": p_kg_acordado, 
                "subtotal": subtot_f
            })

        obs_rec = st.text_area("Observaciones de la Recepción", key="rec_obs")
        saldo_pendiente = max(0.0, valor_total_fruta - monto_abonado)

        st.markdown(f"### 💵 **TOTAL RECEPCIÓN: ${valor_total_fruta:,.2f}** | Canastillas Recibidas: **{canastillas_acum} Uds** | Saldo Pendiente: **${saldo_pendiente:,.2f}**")

        btn_guardar_rec = st.form_submit_button("📥 Registrar Recepción en Bodega")

    if btn_guardar_rec:
        if prov_rec and valor_total_fruta > 0:
            conn = sqlite3.connect("compras_oranges.db")
            c = conn.cursor()
            
            fecha_actual = datetime.now(ZoneInfo("America/Bogota")).strftime("%Y-%m-%d %H:%M:%S")
            peso_neto_total_acum = max(0.0, peso_bruto_acum - tara_acum)

            c.execute("""
                INSERT INTO ordenes_recepcion 
                (id_orden_compra_ref, fecha_ingreso, proveedor, conductor_placa, documento_ref, canastillas_totales, canastillas_devueltas, peso_bruto_total, tara_total, peso_neto_total, costo_flete, valor_total, estado_pago, monto_abonado, saldo_pendiente, observaciones)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (id_oc_ref, fecha_actual, prov_rec, conductor_placa, doc_ref, canastillas_acum, canastillas_dev, peso_bruto_acum, tara_acum, peso_neto_total_acum, costo_flete_ingresado, valor_total_fruta, estado_pago, monto_abonado, saldo_pendiente, obs_rec))
            
            id_rec_creada = c.lastrowid

            for dr in detalles_recepcion:
                c.execute("""
                    INSERT INTO detalle_frutas_orden 
                    (id_orden, fruta, num_canastillas, tara_unit_canastilla, peso_bruto, tara_calculada, kg_danado, kilos_netos, kilos_utiles, precio_kg, subtotal)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (id_rec_creada, dr["fruta"], dr["num_canastillas"], dr["tara_unit_canastilla"], dr["p_bruto"], dr["tara_calculada"], dr["kg_danado"], dr["kg_netos"], dr["kg_utiles"], dr["precio_kg"], dr["subtotal"]))

            conn.commit()
            conn.close()

            st.success(f"🎉 Recepción en Bodega #{id_rec_creada} registrada exitosamente.")
            
            # Botón de Descarga PDF
            pdf_bytes = generar_pdf_recepcion(id_rec_creada)
            if pdf_bytes:
                st.download_button(
                    label="📄 Descargar Comprobante PDF de Recepción",
                    data=pdf_bytes,
                    file_name=f"Comprobante_Recepcion_Oranges_{id_rec_creada}.pdf",
                    mime="application/pdf"
                )
        else:
            st.error("⚠️ Verifica el nombre del proveedor y que la recepción tenga kilos/valores válidos.")

# ==============================================================================
# PESTAÑA 3: DASHBOARD Y FINANZAS
# ==============================================================================
with tab3:
    st.header("📈 Dashboard Financiero y Consolidado de Bodega")

    conn = sqlite3.connect("compras_oranges.db")
    df_rec_dash = pd.read_sql_query("SELECT * FROM ordenes_recepcion", conn)
    df_det_dash = pd.read_sql_query("SELECT * FROM detalle_frutas_orden", conn)
    conn.close()

    if not df_rec_dash.empty:
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        col_m1.metric("Total Invertido en Materia Prima", f"$ {df_rec_dash['valor_total'].sum():,.2f}")
        col_m2.metric("Total Kilos Útiles Recibidos", f"{df_det_dash['kilos_utiles'].sum():,.2f} Kg")
        col_m3.metric("Cuentas por Pagar (Saldos)", f"$ {df_rec_dash['saldo_pendiente'].sum():,.2f}")
        col_m4.metric("Total Canastillas en Fincas/Bodega", f"{df_rec_dash['canastillas_totales'].sum() - df_rec_dash['canastillas_devueltas'].sum()} Uds")

        st.markdown("---")
        col_g1, col_g2 = st.columns(2)

        with col_g1:
            st.subheader("📊 Kilos Útiles Comprados por Fruta")
            df_fruta_summary = df_det_dash.groupby("fruta")["kilos_utiles"].sum().reset_index()
            st.bar_chart(df_fruta_summary, x="fruta", y="kilos_utiles")

        with col_g2:
            st.subheader("💵 Inversión por Proveedor")
            df_prov_summary = df_rec_dash.groupby("proveedor")["valor_total"].sum().reset_index()
            st.bar_chart(df_prov_summary, x="proveedor", y="valor_total")
    else:
        st.info("No hay recepciones registradas para mostrar estadísticas aún.")

# ==============================================================================
# PESTAÑA 4: LOGÍSTICA, CANASTILLAS E HISTORIAL DE PRECIOS
# ==============================================================================
with tab4:
    st.header("🚚 Control Logístico, Canastillas e Historial de Compras")

    subtab_canastillas, subtab_fletes, subtab_precios, subtab_gestion = st.tabs([
        "📦 Control de Canastillas", 
        "🚛 Fletes y Costo Real", 
        "📊 Histórico de Precios",
        "🔍 Consulta y Gestión de Recepciones"
    ])

    # --- SUB-PESTAÑA A: CONTROL DE CANASTILLAS ---
    with subtab_canastillas:
        st.subheader("📦 Balance y Trazabilidad de Canastillas por Proveedor")
        
        conn = sqlite3.connect("compras_oranges.db")
        df_rec_canastillas = pd.read_sql_query("""
            SELECT proveedor, 
                   SUM(canastillas_totales) as recibidas, 
                   SUM(canastillas_devueltas) as devueltas_directas
            FROM ordenes_recepcion GROUP BY proveedor
        """, conn)
        
        df_mov_canastillas = pd.read_sql_query("""
            SELECT proveedor, 
                   SUM(CASE WHEN tipo_movimiento = 'Devolución a Proveedor' THEN cantidad ELSE 0 END) as devueltas_manual,
                   SUM(CASE WHEN tipo_movimiento = 'Ingreso Bodega' THEN cantidad ELSE 0 END) as ingresadas_manual
            FROM control_canastillas GROUP BY proveedor
        """, conn)
        conn.close()

        st.markdown("#### 📊 Saldo Actual de Canastillas")
        if not df_rec_canastillas.empty:
            df_balance = pd.merge(df_rec_canastillas, df_mov_canastillas, on="proveedor", how="outer").fillna(0)
            df_balance['Total Recibidas (En Bodega)'] = df_balance['recibidas'] + df_balance['ingresadas_manual']
            df_balance['Total Devoluciones / Retorno'] = df_balance['devueltas_directas'] + df_balance['devueltas_manual']
            df_balance['Saldo Pendiente por Retornar'] = df_balance['Total Recibidas (En Bodega)'] - df_balance['Total Devoluciones / Retorno']
            
            st.dataframe(
                df_balance[['proveedor', 'Total Recibidas (En Bodega)', 'Total Devoluciones / Retorno', 'Saldo Pendiente por Retornar']], 
                use_container_width=True
            )
        else:
            st.info("No hay registros de canastillas.")

        st.markdown("---")
        st.markdown("#### ➕ Registrar Devolución o Ajuste Manual de Canastillas")
        col_c1, col_c2, col_c3 = st.columns(3)
        with col_c1:
            prov_can = st.text_input("Proveedor", key="can_prov_manual")
        with col_c2:
            tipo_mov = st.selectbox("Tipo de Movimiento", ["Devolución a Proveedor", "Ingreso Bodega", "Ajuste por Pérdida/Daño"])
        with col_c3:
            cant_can = st.number_input("Cantidad de Canastillas", min_value=1, step=1)
        
        obs_can = st.text_input("Observación del movimiento", placeholder="Ej: Conductor recogió canastillas en camión")

        if st.button("💾 Registrar Movimiento de Canastillas"):
            if prov_can and cant_can > 0:
                conn = sqlite3.connect("compras_oranges.db")
                c = conn.cursor()
                c.execute("""
                    INSERT INTO control_canastillas (fecha, proveedor, tipo_movimiento, cantidad, observaciones)
                    VALUES (?, ?, ?, ?, ?)
                """, (datetime.now(ZoneInfo("America/Bogota")).strftime("%Y-%m-%d %H:%M:%S"), prov_can, tipo_mov, cant_can, obs_can))
                conn.commit()
                conn.close()
                st.success("✅ Movimiento de canastillas guardado exitosamente.")
                st.rerun()

    # --- SUB-PESTAÑA B: FLETES Y COSTO REAL ---
    with subtab_fletes:
        st.subheader("🚛 Impacto del Flete en el Costo Real por Kilo")
        st.caption("Muestra el costo real por kilo de la fruta sumando el costo logístico de flete.")

        conn = sqlite3.connect("compras_oranges.db")
        df_fletes = pd.read_sql_query("""
            SELECT r.id_orden, r.fecha_ingreso, r.proveedor, r.documento_ref, 
                   r.peso_neto_total, r.valor_total as valor_fruta, r.costo_flete,
                   (r.valor_total + r.costo_flete) as costo_total_puesto_planta
            FROM ordenes_recepcion r ORDER BY r.id_orden DESC
        """, conn)
        conn.close()

        if not df_fletes.empty:
            df_fletes['Costo Fruta $/Kg'] = df_fletes['valor_fruta'] / df_fletes['peso_neto_total']
            df_fletes['Costo Real $/Kg (con Flete)'] = df_fletes['costo_total_puesto_planta'] / df_fletes['peso_neto_total']
            df_fletes['Sobrecosto Flete $/Kg'] = df_fletes['Costo Real $/Kg (con Flete)'] - df_fletes['Costo Fruta $/Kg']

            st.dataframe(df_fletes[[
                'id_orden', 'fecha_ingreso', 'proveedor', 'documento_ref', 
                'peso_neto_total', 'valor_fruta', 'costo_flete', 
                'Costo Fruta $/Kg', 'Costo Real $/Kg (con Flete)', 'Sobrecosto Flete $/Kg'
            ]], use_container_width=True)

            total_fletes = df_fletes['costo_flete'].sum()
            st.metric("Total Invertido en Fletes / Transporte", f"$ {total_fletes:,.2f}")
        else:
            st.info("No hay recepciones registradas con fletes.")

    # --- SUB-PESTAÑA C: HISTÓRICO DE PRECIOS ---
    with subtab_precios:
        st.subheader("📊 Histórico y Comportamiento de Precios por Fruta")

        conn = sqlite3.connect("compras_oranges.db")
        df_hist_precios = pd.read_sql_query("""
            SELECT d.fruta, r.fecha_ingreso, r.proveedor, d.precio_kg, d.kilos_utiles, d.subtotal
            FROM detalle_frutas_orden d
            JOIN ordenes_recepcion r ON d.id_orden = r.id_orden
            ORDER BY r.fecha_ingreso ASC
        """, conn)
        conn.close()

        if not df_hist_precios.empty:
            fruta_sel_hist = st.selectbox("Selecciona la fruta a analizar:", df_hist_precios['fruta'].unique())
            df_filtrado_fruta = df_hist_precios[df_hist_precios['fruta'] == fruta_sel_hist]

            col_p1, col_p2 = st.columns([2, 1])
            with col_p1:
                st.markdown(f"#### Tendencia de Precio/Kg para **{fruta_sel_hist}**")
                st.line_chart(df_filtrado_fruta, x="fecha_ingreso", y="precio_kg")
            with col_p2:
                st.markdown("#### Comparativo por Proveedor")
                df_prov_comp = df_filtrado_fruta.groupby("proveedor")["precio_kg"].mean().reset_index()
                st.dataframe(df_prov_comp.style.format({"precio_kg": "${:,.2f}"}))
        else:
            st.info("No hay suficiente histórico de compras registrado.")

    # --- SUB-PESTAÑA D: CONSULTA Y GESTIÓN ---
    with subtab_gestion:
        st.subheader("🔍 Buscador y Gestión de Recepciones de Bodega")

        conn = sqlite3.connect("compras_oranges.db")
        df_todas_rec = pd.read_sql_query("SELECT id_orden, fecha_ingreso, proveedor, documento_ref, valor_total, estado_pago, observaciones FROM ordenes_recepcion ORDER BY id_orden DESC", conn)
        conn.close()

        busqueda = st.text_input("🔎 Buscar por Proveedor, Documento o N° Orden:")
        if busqueda:
            df_todas_rec = df_todas_rec[
                df_todas_rec['proveedor'].str.contains(busqueda, case=False, na=False) |
                df_todas_rec['documento_ref'].str.contains(busqueda, case=False, na=False) |
                df_todas_rec['id_orden'].astype(str).str.contains(busqueda, na=False)
            ]

        st.dataframe(df_todas_rec, use_container_width=True)