import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
import io
import os

# Importaciones para la generación profesional de PDF
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

st.set_page_config(page_title="The Oranges - Control de Compras y Bodega", layout="wide")
st.title("🍊 Sistema de Control de Compras y Bodega")

# ----------------- BASE DE DATOS Y AUTO-MIGRACIÓN -----------------

def init_db():
    conn = sqlite3.connect("compras_oranges.db")
    c = conn.cursor()
    
    # 1. Tabla Encabezado de Orden de Compra Semanal
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

    # 2. Tabla Detalle de Frutas y Calidades por Orden de Compra
    c.execute("PRAGMA table_info(detalle_orden_compra)")
    cols = [column[1] for column in c.fetchall()]
    if cols and "modo_precio" not in cols:
        c.execute("DROP TABLE detalle_orden_compra")

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

    # 3. Tabla Principal de Entradas a Bodega (Recepción)
    c.execute("""
    CREATE TABLE IF NOT EXISTS ordenes_recepcion (
        id_orden INTEGER PRIMARY KEY AUTOINCREMENT,
        id_orden_compra_ref INTEGER,
        fecha_ingreso DATETIME NOT NULL,
        proveedor TEXT NOT NULL,
        conductor_placa TEXT,
        documento_ref TEXT,
        canastillas_totales INTEGER DEFAULT 0,
        peso_bruto_total REAL DEFAULT 0,
        tara_total REAL DEFAULT 0,
        peso_neto_total REAL DEFAULT 0,
        valor_total REAL NOT NULL,
        estado_pago TEXT NOT NULL,
        monto_abonado REAL DEFAULT 0,
        saldo_pendiente REAL DEFAULT 0,
        observaciones TEXT,
        FOREIGN KEY (id_orden_compra_ref) REFERENCES ordenes_compra_semanal (id_orden_compra)
    )
    """)

    # 4. Tabla Detalle de Frutas en Recepción (Bodega)
    c.execute("""
    CREATE TABLE IF NOT EXISTS detalle_frutas_orden (
        id_detalle INTEGER PRIMARY KEY AUTOINCREMENT,
        id_orden INTEGER NOT NULL,
        fruta TEXT NOT NULL,
        kg_primera REAL DEFAULT 0,
        precio_primera REAL DEFAULT 0,
        kg_segunda REAL DEFAULT 0,
        precio_segunda REAL DEFAULT 0,
        kg_tercera REAL DEFAULT 0,
        precio_tercera REAL DEFAULT 0,
        kilos_netos REAL NOT NULL,
        precio_kg REAL NOT NULL,
        subtotal REAL NOT NULL,
        FOREIGN KEY (id_orden) REFERENCES ordenes_recepcion (id_orden)
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

# ----------------- FUNCIONES DE GENERACIÓN DE PDF -----------------

def exportar_orden_compra_pdf(encabezado, detalle):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    story = []
    styles = getSampleStyleSheet()
    
    # Obtener hora exacta de Colombia
    fecha_colombia = datetime.now(ZoneInfo("America/Bogota"))
    
    titulo_estilo = ParagraphStyle('TituloPDF', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=18, textColor=colors.HexColor('#E65100'), spaceAfter=5, alignment=1)
    subtitulo_estilo = ParagraphStyle('SubtituloPDF', parent=styles['Normal'], fontName='Helvetica', fontSize=10, textColor=colors.HexColor('#555555'), spaceAfter=15, alignment=1)
    seccion_estilo = ParagraphStyle('SeccionPDF', fontName='Helvetica-Bold', fontSize=11, textColor=colors.HexColor('#E65100'), spaceBefore=10, spaceAfter=6)
    normal_bold = ParagraphStyle('NormalBold', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, textColor=colors.HexColor('#222222'))
    normal_text = ParagraphStyle('NormalText', parent=styles['Normal'], fontName='Helvetica', fontSize=9, textColor=colors.HexColor('#333333'))
    
    story.append(Paragraph("🍊 THE ORANGES S.A.S.", titulo_estilo))
    story.append(Paragraph("ORDEN OFICIAL DE COMPRA MULTI-FRUTA Y CALIDADES", subtitulo_estilo))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#E65100'), spaceAfter=15))
    
    datos_generales = [
        [Paragraph("N° Orden Compra:", normal_bold), Paragraph(f"OC-{encabezado['id_orden']:04d}", normal_text), Paragraph("ID Semana:", normal_bold), Paragraph(encabezado['id_semana'], normal_text)],
        [Paragraph("Proveedor:", normal_bold), Paragraph(encabezado['proveedor'], normal_text), Paragraph("Fecha Emisión:", normal_bold), Paragraph(fecha_colombia.strftime("%d/%m/%Y"), normal_text)],
        [Paragraph("Vigencia Desde:", normal_bold), Paragraph(str(encabezado['fecha_inicio']), normal_text), Paragraph("Vigencia Hasta:", normal_bold), Paragraph(str(encabezado['fecha_fin']), normal_text)]
    ]
    t_generales = Table(datos_generales, colWidths=[110, 150, 110, 160])
    t_generales.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('LINEBELOW', (0,0), (-1,-1), 0.5, colors.HexColor('#E0E0E0'))]))
    story.append(t_generales)
    story.append(Spacer(1, 15))
    
    story.append(Paragraph("DESGLOSE DE FRUTAS Y CALIDADES PACTADAS", seccion_estilo))
    datos_tabla = [[Paragraph("Fruta / Calidad", normal_bold), Paragraph("Cantidad (Kg)", normal_bold), Paragraph("Precio Pactado ($/Kg)", normal_bold), Paragraph("Subtotal Estimado ($)", normal_bold)]]
    
    total_kilos_pactados = 0.0
    total_valor_pactado = 0.0
    for f in detalle:
        if f['modo'] == "Desglosado por Calidad":
            datos_tabla.append([Paragraph(f"<b>{f['fruta']}</b> (Consolidado)", normal_bold), Paragraph(f"{f['cantidad']:,.2f} Kg", normal_bold), Paragraph(f"Prom: $ {f['precio_prom']:,.2f}", normal_bold), Paragraph(f"$ {f['subtotal']:,.2f}", normal_bold)])
            if f['kg_1'] > 0: datos_tabla.append([Paragraph("   • 🥇 Primera (1ra)", normal_text), Paragraph(f"{f['kg_1']:,.2f} Kg", normal_text), Paragraph(f"$ {f['prec_1']:,.2f}", normal_text), Paragraph(f"$ {f['kg_1']*f['prec_1']:,.2f}", normal_text)])
            if f['kg_2'] > 0: datos_tabla.append([Paragraph("   • 🥈 Segunda (2da)", normal_text), Paragraph(f"{f['kg_2']:,.2f} Kg", normal_text), Paragraph(f"$ {f['prec_2']:,.2f}", normal_text), Paragraph(f"$ {f['kg_2']*f['prec_2']:,.2f}", normal_text)])
            if f['kg_3'] > 0: datos_tabla.append([Paragraph("   • 🥉 Tercera (3ra)", normal_text), Paragraph(f"{f['kg_3']:,.2f} Kg", normal_text), Paragraph(f"$ {f['prec_3']:,.2f}", normal_text), Paragraph(f"$ {f['kg_3']*f['prec_3']:,.2f}", normal_text)])
        else:
            datos_tabla.append([Paragraph(f"<b>{f['fruta']}</b> (Única)", normal_text), Paragraph(f"{f['cantidad']:,.2f} Kg", normal_text), Paragraph(f"$ {f['precio_prom']:,.2f}", normal_text), Paragraph(f"$ {f['subtotal']:,.2f}", normal_text)])
            
        total_kilos_pactados += f['cantidad']
        total_valor_pactado += f['subtotal']
        
    datos_tabla.append([Paragraph("TOTAL GENERAL PROGRAMADO", normal_bold), Paragraph(f"{total_kilos_pactados:,.2f} Kg", normal_bold), Paragraph("-", normal_bold), Paragraph(f"$ {total_valor_pactado:,.2f}", normal_bold)])
    
    t_desglose = Table(datos_tabla, colWidths=[170, 110, 120, 130])
    t_desglose.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F5F5F5')), ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CCCCCC')), ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#FFE0B2'))]))
    story.append(t_desglose)
    story.append(Spacer(1, 25))
    
    # ----------------- BLOQUE DE FIRMA ÚNICA LUIS ALBERTO GARCIA -----------------
    story.append(Paragraph("AUTORIZACIÓN Y FIRMA", seccion_estilo))
    
    ruta_firma_imagen = "firma_luis.png"
    if os.path.exists(ruta_firma_imagen):
        img_firma = Image(ruta_firma_imagen, width=140, height=50)
        col_firma = [img_firma, Paragraph("__________________________________", normal_bold)]
    else:
        col_firma = [Paragraph("<b><i>[ FIRMADO DIGITALMENTE ]</i></b>", ParagraphStyle('FirmaDig', parent=styles['Normal'], fontName='Helvetica-BoldOblique', fontSize=10, textColor=colors.HexColor('#1B5E20'))),
                     Paragraph("__________________________________", normal_bold)]

    texto_firmante = Paragraph(
        "<b>LUIS ALBERTO GARCÍA</b><br/>"
        "<b>Cargo:</b> Dirección de Compras / Operaciones<br/>"
        "<b>Empresa:</b> The Oranges S.A.S.<br/>"
        f"<b>Fecha de Autorización:</b> {fecha_colombia.strftime('%d/%m/%Y %I:%M %p')}",
        normal_text
    )

    tabla_firmas_datos = [
        [col_firma[0]],
        [col_firma[1]],
        [texto_firmante]
    ]
    
    t_firmas = Table(tabla_firmas_datos, colWidths=[300])
    t_firmas.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'BOTTOM'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2)
    ]))
    
    story.append(t_firmas)
    
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def exportar_soporte_bascula_pdf(orden_info, lista_frutas):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    story = []
    styles = getSampleStyleSheet()
    
    titulo_estilo = ParagraphStyle('TituloPDF', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=18, textColor=colors.HexColor('#2E7D32'), spaceAfter=5, alignment=1)
    subtitulo_estilo = ParagraphStyle('SubtituloPDF', parent=styles['Normal'], fontName='Helvetica', fontSize=10, textColor=colors.HexColor('#555555'), spaceAfter=15, alignment=1)
    seccion_estilo = ParagraphStyle('SeccionPDF', fontName='Helvetica-Bold', fontSize=11, textColor=colors.HexColor('#2E7D32'), spaceBefore=10, spaceAfter=6)
    normal_bold = ParagraphStyle('NormalBold', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, textColor=colors.HexColor('#222222'))
    normal_text = ParagraphStyle('NormalText', parent=styles['Normal'], fontName='Helvetica', fontSize=9, textColor=colors.HexColor('#333333'))
    
    story.append(Paragraph("🍊 THE ORANGES S.A.S.", titulo_estilo))
    story.append(Paragraph("SOPORTE OFICIAL DE BÁSCULA Y RECEPCIÓN DE FRUTA", subtitulo_estilo))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#2E7D32'), spaceAfter=15))
    
    datos_generales = [
        [Paragraph("N° Recepción:", normal_bold), Paragraph(f"REC-{orden_info['id_orden']:04d}", normal_text), Paragraph("Fecha / Hora:", normal_bold), Paragraph(str(orden_info['fecha']), normal_text)],
        [Paragraph("Proveedor:", normal_bold), Paragraph(orden_info['proveedor'], normal_text), Paragraph("Doc. / Factura:", normal_bold), Paragraph(orden_info['documento'] if orden_info['documento'] else "N/A", normal_text)],
        [Paragraph("Conductor / Placa:", normal_bold), Paragraph(orden_info['conductor'] if orden_info['conductor'] else "N/A", normal_text), Paragraph("Condición Pago:", normal_bold), Paragraph(orden_info['estado_pago'], normal_bold)]
    ]
    t_generales = Table(datos_generales, colWidths=[100, 160, 110, 160])
    t_generales.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('LINEBELOW', (0,0), (-1,-1), 0.5, colors.HexColor('#E0E0E0'))]))
    story.append(t_generales)
    story.append(Spacer(1, 10))
    
    if orden_info['canastillas'] > 0:
        story.append(Paragraph("DATOS DE PESAJE EN BÁSCULA", seccion_estilo))
        datos_bascula = [
            [Paragraph("Canastillas Pesadas", normal_bold), Paragraph("Peso Bruto", normal_bold), Paragraph("Tara Descontada", normal_bold), Paragraph("Peso Neto Real", normal_bold)],
            [Paragraph(f"{orden_info['canastillas']} Unidades", normal_text), Paragraph(f"{orden_info['bruto']:.2f} Kg", normal_text), Paragraph(f"- {orden_info['tara']:.2f} Kg", normal_text), Paragraph(f"{orden_info['neto']:.2f} Kg", normal_bold)]
        ]
        t_bascula = Table(datos_bascula, colWidths=[130, 130, 130, 140])
        t_bascula.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F5F5F5')), ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CCCCCC')), ('BACKGROUND', (0,1), (-1,1), colors.HexColor('#E8F5E9'))]))
        story.append(t_bascula)
        story.append(Spacer(1, 10))
    
    story.append(Paragraph("DETALLE DE FRUTAS Y CALIDADES RECIBIDAS", seccion_estilo))
    datos_tabla = [[Paragraph("Fruta / Materia Prima", normal_bold), Paragraph("Kilos Netos (Kg)", normal_bold), Paragraph("Precio / Kg ($)", normal_bold), Paragraph("Subtotal ($)", normal_bold)]]
    for f in lista_frutas:
        datos_tabla.append([Paragraph(f['fruta'], normal_text), Paragraph(f"{f['kilos']:,.2f} Kg", normal_text), Paragraph(f"$ {f['precio']:,.2f}", normal_text), Paragraph(f"$ {f['subtotal']:,.2f}", normal_text)])
    
    t_desglose = Table(datos_tabla, colWidths=[150, 130, 120, 130])
    t_desglose.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.HexColor('#E8F5E9')), ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CCCCCC'))]))
    story.append(t_desglose)
    story.append(Spacer(1, 10))
    
    story.append(Paragraph("RESUMEN FINANCIERO", seccion_estilo))
    datos_pago = [
        [Paragraph("VALOR TOTAL DE LA ENTREGA:", normal_bold), Paragraph(f"$ {orden_info['valor_total']:,.2f}", normal_bold)],
        [Paragraph("Monto Abonado / Cancelado:", normal_text), Paragraph(f"$ {orden_info['monto_abonado']:,.2f}", normal_text)],
        [Paragraph("SALDO PENDIENTE POR PAGAR:", normal_bold), Paragraph(f"$ {orden_info['saldo_pendiente']:,.2f}", normal_bold)]
    ]
    t_pago = Table(datos_pago, colWidths=[370, 160])
    t_pago.setStyle(TableStyle([('LINEBELOW', (0,0), (-1,-1), 0.5, colors.HexColor('#E0E0E0')), ('BACKGROUND', (0,2), (-1,2), colors.HexColor('#FFEBEE'))]))
    story.append(t_pago)
    
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


# ----------------- ESTRUCTURA DE PESTAÑAS -----------------

tab1, tab2, tab3 = st.tabs([
    "📋 Planeación Semanal (Orden de Compra Multi-Fruta y Calidades)", 
    "🚛 Recepción de Fruta y Báscula (Bodega)", 
    "📈 Dashboard y Gestión de Costos"
])

# ----------------- PESTAÑA 1: ORDEN DE COMPRA (MULTI-FRUTA Y CALIDADES) -----------------
with tab1:
    st.header("📄 Formato Orden de Compra Semanal")
    
    if 'ultima_oc_creada' not in st.session_state:
        st.session_state.ultima_oc_creada = None

    col_oc1, col_oc2, col_oc3 = st.columns(3)
    with col_oc1: id_semana = st.text_input("ID de la Semana (Ej: SEM-2026-29)", placeholder="SEM-YYYY-WW")
    with col_oc2: proveedor_oc = st.text_input("Nombre del Proveedor", placeholder="Ej: Jorge Ever Toro")
    with col_oc3:
        f_inc = st.date_input("Vigencia Desde")
        f_fin = st.date_input("Vigencia Hasta")

    st.markdown("---")
    st.markdown("#### 🍉 Frutas a Programar en la Orden de Compra")

    if "num_frutas_oc" not in st.session_state: st.session_state.num_frutas_oc = 1

    col_b1, col_b2 = st.columns([2, 10])
    with col_b1:
        if st.button("➕ Agregar Otra Fruta a la Orden"): st.session_state.num_frutas_oc += 1
    with col_b2:
        if st.session_state.num_frutas_oc > 1 and st.button("➖ Quitar Última Fruta"): st.session_state.num_frutas_oc -= 1

    frutas_oc_capturadas = []
    total_valor_oc = 0.0

    for i in range(st.session_state.num_frutas_oc):
        st.markdown(f"### 🍇 Fruta #{i+1}")
        col_oc_f1, col_oc_f2 = st.columns([3, 3])
        with col_oc_f1:
            fruta_sel = st.selectbox(f"Selecciona Fruta #{i+1}", LISTA_FRUTAS, key=f"oc_fruta_sel_{i}")
            fruta_i = fruta_sel
            if fruta_sel == "OTRA (Escribir nueva...)":
                fruta_i = st.text_input(f"Nombre Fruta #{i+1}", key=f"oc_fruta_custom_{i}").strip().upper()
        with col_oc_f2:
            modo_precio = st.radio(f"Modalidad de precio para {fruta_i}:", ["Precio Único / Global", "Desglosado por Calidad"], key=f"oc_modo_{i}", horizontal=True)

        kg_1, prec_1, kg_2, prec_2, kg_3, prec_3 = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
        cant_tot_i, precio_prom_i, subtot_i = 0.0, 0.0, 0.0

        if modo_precio == "Precio Único / Global":
            c_u1, c_u2, c_u3 = st.columns(3)
            with c_u1: cant_tot_i = st.number_input("Cantidad Total (Kg)", min_value=0.0, step=100.0, key=f"oc_cant_u_{i}")
            with c_u2: precio_prom_i = st.number_input("Precio Pactado/Kg ($)", min_value=0.0, step=50.0, key=f"oc_prec_u_{i}")
            subtot_i = cant_tot_i * precio_prom_i
            with c_u3: st.markdown(f"**Subtotal Fruta:**\n# $ {subtot_i:,.2f}")
        else:
            st.caption("Desglose por Calidades:")
            col_c1, col_c2, col_c3 = st.columns(3)
            with col_c1:
                kg_1 = st.number_input("Kg Primera (1ra)", min_value=0.0, step=50.0, key=f"oc_kg1_{i}")
                prec_1 = st.number_input("Precio 1ra ($/Kg)", min_value=0.0, step=50.0, key=f"oc_pr1_{i}")
            with col_c2:
                kg_2 = st.number_input("Kg Segunda (2da)", min_value=0.0, step=50.0, key=f"oc_kg2_{i}")
                prec_2 = st.number_input("Precio 2da ($/Kg)", min_value=0.0, step=50.0, key=f"oc_pr2_{i}")
            with col_c3:
                kg_3 = st.number_input("Kg Tercera (3ra)", min_value=0.0, step=50.0, key=f"oc_kg3_{i}")
                prec_3 = st.number_input("Precio 3ra ($/Kg)", min_value=0.0, step=50.0, key=f"oc_pr3_{i}")

            cant_tot_i = kg_1 + kg_2 + kg_3
            subtot_i = (kg_1 * prec_1) + (kg_2 * prec_2) + (kg_3 * prec_3)
            precio_prom_i = (subtot_i / cant_tot_i) if cant_tot_i > 0 else 0.0
            st.info(f"📊 **Subtotal {fruta_i}:** {cant_tot_i:,.1f} Kg | Precio Promedio: ${precio_prom_i:,.2f}/Kg | **Total: $ {subtot_i:,.2f}**")

        total_valor_oc += subtot_i
        frutas_oc_capturadas.append({
            "fruta": fruta_i, "modo": modo_precio,
            "kg_1": kg_1, "prec_1": prec_1, "kg_2": kg_2, "prec_2": prec_2, "kg_3": kg_3, "prec_3": prec_3,
            "cantidad": cant_tot_i, "precio_prom": precio_prom_i, "subtotal": subtot_i
        })
        st.markdown("---")

    obs_oc = st.text_area("Observaciones o Condiciones Especiales del Pedido")

    if st.button("💾 Guardar y Emitir Orden de Compra", type="primary", use_container_width=True):
        if id_semana and proveedor_oc and total_valor_oc > 0:
            conn = sqlite3.connect("compras_oranges.db")
            c = conn.cursor()
            c.execute("""
                INSERT INTO ordenes_compra_semanal (id_semana, proveedor, fecha_inicio, fecha_fin, observaciones)
                VALUES (?, ?, ?, ?, ?)
            """, (id_semana, proveedor_oc, f_inc, f_fin, obs_oc))
            
            id_oc_creada = c.lastrowid
            for item in frutas_oc_capturadas:
                if item['cantidad'] > 0:
                    c.execute("""
                        INSERT INTO detalle_orden_compra 
                        (id_orden_compra, fruta, modo_precio, kg_primera, precio_primera, kg_segunda, precio_segunda, kg_tercera, precio_tercera, cantidad_total, precio_promedio, subtotal_pactado)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (id_oc_creada, item['fruta'], item['modo'], item['kg_1'], item['prec_1'], item['kg_2'], item['prec_2'], item['kg_3'], item['prec_3'], item['cantidad'], item['precio_prom'], item['subtotal']))
            conn.commit()
            conn.close()
            
            encabezado = {"id_orden": id_oc_creada, "id_semana": id_semana, "proveedor": proveedor_oc, "fecha_inicio": f_inc, "fecha_fin": f_fin}
            st.session_state.ultima_oc_creada = (encabezado, frutas_oc_capturadas)
            st.session_state.num_frutas_oc = 1
            st.success(f"✅ Orden de Compra OC-{id_oc_creada:04d} emitida exitosamente.")
            st.rerun()

    if st.session_state.ultima_oc_creada:
        enc, det = st.session_state.ultima_oc_creada
        col_pdf_oc, col_wa_oc = st.columns(2)
        with col_pdf_oc:
            pdf_bytes_oc = exportar_orden_compra_pdf(enc, det)
            st.download_button("📄 Descargar Orden de Compra (PDF)", data=pdf_bytes_oc, file_name=f"Orden_Compra_OC_{enc['id_orden']:04d}_{enc['proveedor']}.pdf", mime="application/pdf")
        with col_wa_oc:
            desglose_oc_wa = ""
            for item in det:
                desglose_oc_wa += f"• *{item['fruta']}*: {item['cantidad']:,.0f} Kg = ${item['subtotal']:,.2f}\n"
                if item['modo'] == "Desglosado por Calidad":
                    if item['kg_1'] > 0: desglose_oc_wa += f"   - 1ra: {item['kg_1']:,.0f} Kg @ ${item['prec_1']:,.0f}\n"
                    if item['kg_2'] > 0: desglose_oc_wa += f"   - 2da: {item['kg_2']:,.0f} Kg @ ${item['prec_2']:,.0f}\n"
                    if item['kg_3'] > 0: desglose_oc_wa += f"   - 3ra: {item['kg_3']:,.0f} Kg @ ${item['prec_3']:,.0f}\n"
            
            texto_wa_oc = f"*🍊 THE ORANGES - ORDEN DE COMPRA MULTI-FRUTA*\n*OC-{enc['id_orden']:04d}* | {enc['proveedor']}\n*Semana:* {enc['id_semana']}\n------------------------------------------------\n{desglose_oc_wa}------------------------------------------------\n*VALOR ESTIMADO PACTADO:* *${sum([x['subtotal'] for x in det]):,.2f}*"
            st.text_area("Copia el pedido para WhatsApp:", value=texto_wa_oc, height=150)

# ----------------- PESTAÑA 2: RECEPCIÓN DE BODEGA VINCULADA -----------------
with tab2:
    st.header("🚛 Recepción de Fruta en Bodega (Vinculada a Orden de Compra)")
    
    if 'ultima_orden_guardada' not in st.session_state: st.session_state.ultima_orden_guardada = None

    conn = sqlite3.connect("compras_oranges.db")
    df_oc_activas = pd.read_sql_query("""
        SELECT id_orden_compra, id_semana, proveedor 
        FROM ordenes_compra_semanal ORDER BY id_orden_compra DESC
    """, conn)
    conn.close()

    id_oc_seleccionada = None
    frutas_sugeridas_orden = []

    if df_oc_activas.empty:
        st.warning("⚠️ No hay Órdenes de Compra registradas. Crea una en la Pestaña 1 primero.")
    else:
        opciones_oc = df_oc_activas.apply(lambda r: f"OC #{r['id_orden_compra']:04d} | {r['id_semana']} - Proveedor: {r['proveedor']}", axis=1).tolist()
        sel_oc = st.selectbox("Selecciona la Orden de Compra Vinculada para la Recepción:", opciones_oc)
        
        id_oc_seleccionada = int(sel_oc.split(" | ")[0].replace("OC #", ""))
        
        conn = sqlite3.connect("compras_oranges.db")
        c = conn.cursor()
        c.execute("SELECT fruta, modo_precio, kg_primera, precio_primera, kg_segunda, precio_segunda, kg_tercera, precio_tercera, cantidad_total, precio_promedio FROM detalle_orden_compra WHERE id_orden_compra = ?", (id_oc_seleccionada,))
        frutas_sugeridas_orden = c.fetchall()
        
        c.execute("SELECT proveedor FROM ordenes_compra_semanal WHERE id_orden_compra = ?", (id_oc_seleccionada,))
        prov_nombre_sugerido = c.fetchone()[0]
        conn.close()

        st.markdown("---")
        col_g1, col_g2, col_g3 = st.columns(3)
        with col_g1: proveedor_recep = st.text_input("Proveedor", value=prov_nombre_sugerido, key="rec_prov_vinc")
        with col_g2: fecha_ingreso = st.datetime_input("Fecha y Hora", value=datetime.now(ZoneInfo("America/Bogota")), key="rec_f_vinc")
        with col_g3: doc_ref = st.text_input("N° Factura / DS / Remisión", placeholder="Ej: DS-104", key="rec_doc_vinc")

        conductor_placa = st.text_input("Conductor / Placa Vehículo", placeholder="Ej: ABC-123", key="rec_cond_vinc")

        # Calculadora de Báscula
        st.markdown("#### 🧮 Calculadora de Pesaje por Canastillas (Báscula)")
        col_c1, col_c2 = st.columns([1, 2])
        with col_c1: peso_tara_unit = st.number_input("Peso Tara por Canastilla (Kg)", min_value=0.0, value=2.0, step=0.1, key="rec_tara_vinc")
        with col_c2: pesos_texto = st.text_area("Pesos de Canastillas", placeholder="Ej: 23, 110*5, 45*2, 22.8", height=70, key="rec_txt_vinc")

        conteo_canastillas, bruto_total, tara_total, neto_calculado_bascula = 0, 0.0, 0.0, 0.0
        if pesos_texto:
            try:
                partes = [x.strip() for x in pesos_texto.split(",") if x.strip() != ""]
                for p in partes:
                    if "*" in p:
                        subparts = p.split("*")
                        bruto_total += float(subparts[0].strip())
                        conteo_canastillas += int(subparts[1].strip())
                    else:
                        bruto_total += float(p)
                        conteo_canastillas += 1
                tara_total = conteo_canastillas * peso_tara_unit
                neto_calculado_bascula = max(0.0, bruto_total - tara_total)
                st.info(f"📋 Báscula: {conteo_canastillas} canastillas | Bruto: {bruto_total:.2f} Kg | Tara: -{tara_total:.2f} Kg | **Neto: {neto_calculado_bascula:.2f} Kg**")
            except Exception: st.error("Error en formato de báscula")

        st.markdown("---")
        st.markdown("#### 🍉 Pesaje Real de Frutas y Calidades Recibidas")

        frutas_recepcion_capturadas = []
        valor_total_recepcion = 0.0

        for idx, (f_nom, f_modo, f_kg1, f_pr1, f_kg2, f_pr2, f_kg3, f_pr3, f_cant, f_prom) in enumerate(frutas_sugeridas_orden):
            st.markdown(f"### 🍇 {f_nom} *(Pactado total: {f_cant:,.0f} Kg)*")
            
            if f_modo == "Desglosado por Calidad":
                c_r1, c_r2, c_r3 = st.columns(3)
                with c_r1:
                    rk_1 = st.number_input(f"Kg Reales Primera (1ra)", min_value=0.0, value=float(f_kg1), step=10.0, key=f"rk1_{idx}")
                    rp_1 = st.number_input(f"Precio 1ra ($/Kg)", min_value=0.0, value=float(f_pr1), step=50.0, key=f"rp1_{idx}")
                with c_r2:
                    rk_2 = st.number_input(f"Kg Reales Segunda (2da)", min_value=0.0, value=float(f_kg2), step=10.0, key=f"rk2_{idx}")
                    rp_2 = st.number_input(f"Precio 2da ($/Kg)", min_value=0.0, value=float(f_pr2), step=50.0, key=f"rp2_{idx}")
                with c_r3:
                    rk_3 = st.number_input(f"Kg Reales Tercera (3ra)", min_value=0.0, value=float(f_kg3), step=10.0, key=f"rk3_{idx}")
                    rp_3 = st.number_input(f"Precio 3ra ($/Kg)", min_value=0.0, value=float(f_pr3), step=50.0, key=f"rp3_{idx}")

                tot_k_f = rk_1 + rk_2 + rk_3
                subt_f = (rk_1 * rp_1) + (rk_2 * rp_2) + (rk_3 * rp_3)
                pr_prom_f = (subt_f / tot_k_f) if tot_k_f > 0 else 0.0
                st.info(f"Subtotal {f_nom}: {tot_k_f:,.1f} Kg | **Total Liquidado: $ {subt_f:,.2f}**")
                
                valor_total_recepcion += subt_f
                frutas_recepcion_capturadas.append({"fruta": f_nom, "kilos": tot_k_f, "precio": pr_prom_f, "subtotal": subt_f})
            else:
                col_rf1, col_rf2, col_rf3 = st.columns(3)
                with col_rf1:
                    kilos_reales = st.number_input(f"Kilos Reales Recibidos ({f_nom})", min_value=0.0, value=float(neto_calculado_bascula if len(frutas_sugeridas_orden) == 1 else f_cant), step=10.0, key=f"vinc_k_{idx}")
                with col_rf2:
                    precio_real = st.number_input(f"Precio Liquidado/Kg ($)", min_value=0.0, value=float(f_prom), step=50.0, key=f"vinc_p_{idx}")
                with col_rf3:
                    subt_real = kilos_reales * precio_real
                    st.markdown(f"**Subtotal Liquidado:**\n# $ {subt_real:,.2f}")
                    valor_total_recepcion += subt_real
                    frutas_recepcion_capturadas.append({"fruta": f_nom, "kilos": kilos_reales, "precio": precio_real, "subtotal": subt_real})

        st.markdown("---")
        st.markdown("#### 💳 Condición de Pago de la Entrega")
        col_p1, col_p2, col_p3 = st.columns(3)
        with col_p1: condicion_pago = st.selectbox("Estado de Pago", ["A Crédito (Pendiente 100%)", "Abonado (Pago parcial)", "Contado / Cancelado ($0 Pendiente)"], key="vinc_cond_pago")
        
        monto_abonado = 0.0
        if condicion_pago == "Abonado (Pago parcial)":
            with col_p2: monto_abonado = st.number_input("Monto Abonado ($)", min_value=0.0, max_value=float(valor_total_recepcion), step=50000.0, key="vinc_monto_ab")
        elif condicion_pago == "Contado / Cancelado ($0 Pendiente)":
            monto_abonado = valor_total_recepcion

        saldo_pendiente = max(0.0, valor_total_recepcion - monto_abonado)
        with col_p3:
            st.markdown(f"### **Total Entrega:** $ {valor_total_recepcion:,.2f}")
            st.markdown(f"### **Saldo Pendiente:** :red[$ {saldo_pendiente:,.2f}]")

        observaciones = st.text_area("Observaciones o Novedades de Calidad en Bodega", key="vinc_obs")

        if st.button("💾 Guardar Ingreso a Bodega y Generar Soporte", type="primary", use_container_width=True):
            if proveedor_recep and valor_total_recepcion > 0:
                conn = sqlite3.connect("compras_oranges.db")
                c = conn.cursor()
                c.execute("""
                    INSERT INTO ordenes_recepcion (id_orden_compra_ref, fecha_ingreso, proveedor, conductor_placa, documento_ref, canastillas_totales, peso_bruto_total, tara_total, peso_neto_total, valor_total, estado_pago, monto_abonado, saldo_pendiente, observaciones)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (id_oc_seleccionada, fecha_ingreso.strftime("%Y-%m-%d %H:%M:%S"), proveedor_recep, conductor_placa, doc_ref, conteo_canastillas, bruto_total, tara_total, sum([item['kilos'] for item in frutas_recepcion_capturadas]), valor_total_recepcion, condicion_pago, monto_abonado, saldo_pendiente, observaciones))
                
                id_orden_creada = c.lastrowid
                for item in frutas_recepcion_capturadas:
                    if item['kilos'] > 0:
                        c.execute("INSERT INTO detalle_frutas_orden (id_orden, fruta, kilos_netos, precio_kg, subtotal) VALUES (?, ?, ?, ?, ?)", (id_orden_creada, item['fruta'], item['kilos'], item['precio'], item['subtotal']))
                conn.commit()
                conn.close()
                
                orden_info = {"id_orden": id_orden_creada, "fecha": fecha_ingreso.strftime("%d/%m/%Y %I:%M %p"), "proveedor": proveedor_recep, "documento": doc_ref, "conductor": conductor_placa, "canastillas": conteo_canastillas, "bruto": bruto_total, "tara": tara_total, "neto": sum([item['kilos'] for item in frutas_recepcion_capturadas]), "valor_total": valor_total_recepcion, "estado_pago": condicion_pago, "monto_abonado": monto_abonado, "saldo_pendiente": saldo_pendiente, "observaciones": observaciones}
                st.session_state.ultima_orden_guardada = (orden_info, frutas_recepcion_capturadas)
                st.success(f"✅ Ingreso REC-{id_orden_creada:04d} registrado exitosamente.")
                st.rerun()

        if st.session_state.ultima_orden_guardada:
            ord_info, lista_f = st.session_state.ultima_orden_guardada
            col_pdf, col_wa = st.columns(2)
            with col_pdf:
                pdf_bytes = exportar_soporte_bascula_pdf(ord_info, lista_f)
                st.download_button("📄 Descargar Soporte Báscula (PDF)", data=pdf_bytes, file_name=f"Soporte_REC_{ord_info['id_orden']:04d}.pdf", mime="application/pdf")
            with col_wa:
                desglose_wa = "".join([f"• {item['fruta']}: {item['kilos']:,.1f} Kg @ ${item['precio']:,.0f} = ${item['subtotal']:,.2f}\n" for item in lista_f])
                texto_wa = f"*🍊 THE ORANGES - SOPORTE DE BODEGA*\n*REC-{ord_info['id_orden']:04d}* | {ord_info['proveedor']}\n{desglose_wa}*TOTAL:* *${ord_info['valor_total']:,.2f}*\n*Saldo Pendiente:* *${ord_info['saldo_pendiente']:,.2f}*"
                st.text_area("Texto para WhatsApp:", value=texto_wa, height=120)

# ----------------- PESTAÑA 3: DASHBOARD DE COSTOS -----------------
with tab3:
    st.header("📈 Dashboard de Inteligencia de Negocio")
    
    conn = sqlite3.connect("compras_oranges.db")
    df_dash = pd.read_sql_query("""
        SELECT d.fruta, o.fecha_ingreso as fecha, d.kilos_netos, d.precio_kg, d.subtotal, o.proveedor
        FROM detalle_frutas_orden d
        JOIN ordenes_recepcion o ON d.id_orden = o.id_orden
    """, conn)
    conn.close()

    if df_dash.empty:
        st.info("ℹ️ Carga frutas en bodega para ver estadísticas visuales.")
    else:
        st.subheader("1. Variación de Precio por Kilo ($/Kg)")
        frutas_disponibles = sorted(list(df_dash['fruta'].unique()))
        sel_f_dash = st.selectbox("Selecciona fruta:", frutas_disponibles)
        df_f_filt = df_dash[df_dash['fruta'] == sel_f_dash].sort_values('fecha')
        if not df_f_filt.empty:
            st.line_chart(df_f_filt, x='fecha', y='precio_kg', use_container_width=True)

        col_g1, col_g2 = st.columns(2)
        with col_g1:
            st.subheader("2. Volumen Comprado por Proveedor (Kg)")
            st.bar_chart(df_dash.groupby('proveedor')['kilos_netos'].sum().reset_index(), x='proveedor', y='kilos_netos', use_container_width=True)
        with col_g2:
            st.subheader("3. Inversión por Fruta ($)")
            st.bar_chart(df_dash.groupby('fruta')['subtotal'].sum().reset_index(), x='fruta', y='subtotal', use_container_width=True)