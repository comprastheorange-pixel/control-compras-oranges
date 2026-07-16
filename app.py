import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import io

# Importaciones para la generación profesional del PDF
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

st.set_page_config(page_title="The Oranges - Control de Compras", layout="wide")
st.title("🍊 Sistema de Control de Compras y Bodega")

def init_db():
    conn = sqlite3.connect("compras_oranges.db")
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS programacion_semanal (
        id_programacion INTEGER PRIMARY KEY AUTOINCREMENT,
        id_semana TEXT NOT NULL,
        fecha_inicio DATE NOT NULL,
        fecha_fin DATE NOT NULL,
        fruta TEXT NOT NULL,
        proveedor TEXT NOT NULL,
        cantidad_pactada REAL NOT NULL,
        precio_pactado REAL NOT NULL
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS ingresos_bodega (
        id_ingreso INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha_ingreso DATE NOT NULL,
        factura_ds TEXT,
        id_semana_ref TEXT NOT NULL,
        fruta TEXT NOT NULL,
        proveedor TEXT NOT NULL,
        cantidad_pactada REAL NOT NULL,
        precio_pactado REAL NOT NULL,
        ingreso_bodega REAL NOT NULL,
        precio_final REAL NOT NULL,
        conductor TEXT,
        observaciones TEXT
    )
    """)
    conn.commit()
    conn.close()

init_db()

# Función profesional para generar el PDF con Sello de Validación Digital
def exportar_recibo_pdf(reg):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=letter, 
        rightMargin=40, 
        leftMargin=40, 
        topMargin=40, 
        bottomMargin=40
    )
    story = []
    styles = getSampleStyleSheet()
    
    # Estilos personalizados
    titulo_estilo = ParagraphStyle(
        'TituloPDF',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        textColor=colors.HexColor('#E65100'), # Naranja corporativo
        spaceAfter=5,
        alignment=1 # Centrado
    )
    subtitulo_estilo = ParagraphStyle(
        'SubtituloPDF',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        textColor=colors.HexColor('#555555'),
        spaceAfter=15,
        alignment=1
    )
    seccion_estilo = ParagraphStyle(
        'SeccionPDF',
        fontName='Helvetica-Bold',
        fontSize=11,
        textColor=colors.HexColor('#E65100'),
        spaceBefore=10,
        spaceAfter=6
    )
    normal_bold = ParagraphStyle(
        'NormalBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        textColor=colors.HexColor('#222222')
    )
    normal_text = ParagraphStyle(
        'NormalText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        textColor=colors.HexColor('#333333')
    )
    
    # 1. ENCABEZADO CORPORATIVO
    story.append(Paragraph("🍊 THE ORANGES S.A.S.", titulo_estilo))
    story.append(Paragraph("SOPORTE DE RECEPCIÓN Y CERTIFICACIÓN DE FRUTA EN BODEGA", subtitulo_estilo))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#E65100'), spaceAfter=15))
    
    # 2. INFORMACIÓN GENERAL DEL RECIBO
    story.append(Paragraph("DATOS GENERALES DE LA ENTREGA", seccion_estilo))
    datos_generales = [
        [Paragraph("Fecha de Ingreso:", normal_bold), Paragraph(reg['Fecha'], normal_text),
         Paragraph("Doc. Soporte / Factura:", normal_bold), Paragraph(reg['Factura_DS'] if reg['Factura_DS'] else "N/A", normal_text)],
        [Paragraph("Proveedor:", normal_bold), Paragraph(reg['Proveedor'], normal_text),
         Paragraph("Fruta Recibida:", normal_bold), Paragraph(reg['Fruta'], normal_text)],
        [Paragraph("Conductor:", normal_bold), Paragraph(reg['Conductor'] if reg['Conductor'] else "N/A", normal_text),
         Paragraph("Estado / Control:", normal_bold), Paragraph("Aprobado en Bodega", normal_text)]
    ]
    t_generales = Table(datos_generales, colWidths=[90, 170, 130, 140])
    t_generales.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('LINEBELOW', (0,0), (-1,-1), 0.5, colors.HexColor('#E0E0E0')),
    ]))
    story.append(t_generales)
    story.append(Spacer(1, 15))
    
    # 3. DETALLE DE PESO Y BÁSCULA
    story.append(Paragraph("DETALLE FÍSICO DE BÁSCULA (PESAJE POR CANASTILLAS)", seccion_estilo))
    
    bruto = f"{reg['Peso_Bruto']:.2f} Kg"
    tara = f"{reg['Tara_Restada']:.2f} Kg"
    neto = f"{reg['Peso_Neto_Entregado']:.2f} Kg"
    precio_u = f"$ {reg['Precio_Kg']:,.2f}"
    total_liq = f"$ {reg['Total_Pagar']:,.2f}"
    
    datos_pesaje = [
        [Paragraph("Concepto de Pesaje", normal_bold), Paragraph("Detalle / Conteo", normal_bold), Paragraph("Peso Evaluado (Kg)", normal_bold)],
        [Paragraph("Total Canastillas Pesadas", normal_text), Paragraph(f"{reg['Canastillas']} Unidades", normal_text), Paragraph("-", normal_text)],
        [Paragraph("Peso Bruto Consolidado", normal_text), Paragraph("Lectura directa báscula", normal_text), Paragraph(bruto, normal_text)],
        [Paragraph("Tara Descontada", normal_text), Paragraph(f"Descuento de Canastilla Vacía", normal_text), Paragraph(f"- {tara}", normal_text)],
        [Paragraph("PESO NETO REAL RECIBIDO", normal_bold), Paragraph("Materia Prima Líquida", normal_bold), Paragraph(neto, normal_bold)],
    ]
    t_pesaje = Table(datos_pesaje, colWidths=[180, 190, 160])
    t_pesaje.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F5F5F5')),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('ALIGN', (2,0), (2,-1), 'RIGHT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CCCCCC')),
        ('BACKGROUND', (0,4), (-1,4), colors.HexColor('#FFE0B2')), # Resaltado neto
    ]))
    story.append(t_pesaje)
    story.append(Spacer(1, 15))
    
    # 4. VALORES DE LIQUIDACIÓN
    story.append(Paragraph("LIQUIDACIÓN FINANCIERA", seccion_estilo))
    datos_valores = [
        [Paragraph("Precio Unitario de Compra (Pactado):", normal_text), Paragraph(precio_u, normal_text)],
        [Paragraph("TOTAL NETO A LIQUIDAR AL PROVEEDOR:", normal_bold), Paragraph(total_liq, normal_bold)]
    ]
    t_valores = Table(datos_valores, colWidths=[370, 160])
    t_valores.setStyle(TableStyle([
        ('ALIGN', (0,0), (0,-1), 'LEFT'),
        ('ALIGN', (1,0), (1,-1), 'RIGHT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('LINEBELOW', (0,0), (-1,-1), 0.5, colors.HexColor('#E0E0E0')),
        ('BACKGROUND', (0,1), (-1,1), colors.HexColor('#FFF3E0')),
    ]))
    story.append(t_valores)
    story.append(Spacer(1, 15))
    
    # 5. OBSERVACIONES
    story.append(Paragraph("OBSERVACIONES Y NOVEDADES", seccion_estilo))
    obs_texto = reg['Observaciones'] if reg['Observaciones'] else "Ninguna novedad registrada en la entrega física."
    t_obs = Table([[Paragraph(obs_texto, normal_text)]], colWidths=[530])
    t_obs.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#FAFAFA')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E0E0E0')),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('TOPPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(t_obs)
    story.append(Spacer(1, 20))
    
    # 6. SECCIÓN DE SELLO DE VALIDACIÓN DIGITAL (REEMPLAZA LAS FIRMAS FÍSICAS)
    hora_actual = datetime.now().strftime("%I:%M %p")
    fecha_actual = datetime.now().strftime("%d/%m/%Y")
    
    sello_texto = (
        f"<b>🔐 DOCUMENTO VALIDADO DIGITALMENTE POR EL SISTEMA DE COMPRAS</b><br/>"
        f"Este soporte certifica que los datos de báscula fueron verificados y cargados al sistema local "
        f"de <b>The Oranges S.A.S.</b> de forma segura.<br/>"
        f"• <b>Responsable de Bodega:</b> Juan Carlos Perlaza<br/>"
        f"• <b>Fecha de Validación:</b> {fecha_actual} a las {hora_actual}."
    )
    
    t_sello = Table([[Paragraph(sello_texto, normal_text)]], colWidths=[530])
    t_sello.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#E8F5E9')), # Verde claro de seguridad
        ('GRID', (0,0), (-1,-1), 1, colors.HexColor('#4CAF50')),      # Borde verde oliva
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
        ('TOPPADDING', (0,0), (-1,-1), 10),
    ]))
    story.append(t_sello)
    
    # Construcción final del documento
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


LISTA_FRUTAS = [
    "CHULUPA", "FRESA", "GUANABANA", "GUAYABA", "LIMON", 
    "LULO", "MANGO", "MARACUYA", "MORA", "NARANJA", 
    "PIÑA", "TOMATE ARBOL", "UVA"
]

tab1, tab2, tab3 = st.tabs(["📋 Planeación Semanal (Compras)", "🚛 Recepción de Fruta (Bodega)", "📊 Control y Conciliación (Contabilidad)"])

# ----------------- PESTAÑA 1: PLANEACIÓN SEMANAL -----------------
with tab1:
    st.header("📄 Formato Orden de Compra (Luis Alberto Garcia)")
    with st.form("form_planeacion", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            id_semana = st.text_input("ID de la Semana (Ej: SEM-2026-29)", placeholder="SEM-YYYY-WW")
            fruta = st.selectbox("Fruta a Programar", LISTA_FRUTAS)
        with col2:
            fecha_inicio = st.date_input("Fecha de la Orden (Inicio)")
            proveedor = st.text_input("Nombre del Proveedor")
        with col3:
            fecha_fin = st.date_input("Fecha Fin de la Orden")
            cantidad_pactada = st.number_input("CANT (Kg)", min_value=0.0, step=10.0)
            precio_pactado = st.number_input("PRECIO Pactado por Kg ($)", min_value=0.0, step=50.0)
            
        submitted = st.form_submit_button("Guardar Orden de Compra")
        if submitted:
            if id_semana and proveedor and cantidad_pactada > 0 and precio_pactado > 0:
                conn = sqlite3.connect("compras_oranges.db")
                c = conn.cursor()
                c.execute("""
                    INSERT INTO programacion_semanal (id_semana, fecha_inicio, fecha_fin, fruta, proveedor, cantidad_pactada, precio_pactado)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (id_semana, fecha_inicio, fecha_fin, fruta, proveedor, cantidad_pactada, precio_pactado))
                conn.commit()
                conn.close()
                st.success(f"✅ Orden de Compra para {fruta} registrada exitosamente.")
            else:
                st.error("⚠️ Por favor completa todos los campos con valores válidos.")

    st.subheader("Historial de Ordenes de Compra")
    conn = sqlite3.connect("compras_oranges.db")
    df_plan = pd.read_sql_query("SELECT id_semana, fecha_inicio as fecha, fruta, proveedor, cantidad_pactada as cant, precio_pactado as precio, (cantidad_pactada * precio_pactado) as total_pactado FROM programacion_semanal", conn)
    conn.close()
    if not df_plan.empty:
        st.dataframe(df_plan, use_container_width=True)

# ----------------- PESTAÑA 2: RECEPCIÓN DE BODEGA -----------------
with tab2:
    st.header("🚛 Ingresos de Compra de Fruta a Bodega (Juan Carlos Perlaza)")
    
    conn = sqlite3.connect("compras_oranges.db")
    df_plan_ref = pd.read_sql_query("SELECT DISTINCT id_semana, fruta, proveedor, cantidad_pactada, precio_pactado FROM programacion_semanal", conn)
    conn.close()
    
    if df_plan_ref.empty:
        st.warning("⚠️ No hay órdenes de compra registradas. Luis Alberto debe ingresar una orden en la pestaña 1 primero.")
    else:
        opciones_ref = df_plan_ref.apply(lambda r: f"{r['id_semana']} | {r['fruta']} - {r['proveedor']}", axis=1).tolist()
        seleccion = st.selectbox("Selecciona la Orden de Compra de Referencia", opciones_ref)
        
        fila_seleccionada = df_plan_ref.iloc[opciones_ref.index(seleccion)]
        
        st.markdown("---")
        st.subheader("🧮 Calculadora de Pesaje por Canastillas (Soporta Tandas)")
        st.markdown("""
        💡 **¿Cómo ingresar los pesos?** Separa cada pesada con comas. 
        * Para pesajes individuales escribe solo el número. Ej: `22.5`
        * Para pesajes en grupo usa un asterisco `*` para indicar cuántas canastillas se subieron juntas. Ej: `110 * 5` (pesaron 110 Kg entre 5 canastillas).
        * *Ejemplo combinado:* `23, 110.5*5, 45*2, 22.8`
        """)
        
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            peso_tara = st.number_input("Peso de una Canastilla Vacía / Tara (Kg)", min_value=0.0, value=2.0, step=0.1)
        with col_c2:
            pesos_texto = st.text_area("Pesos Brutos de Canastillas", placeholder="Ejemplo: 23, 110*5, 45*2, 22.8")

        cantidad_final_calculada = 0.0
        conteo_canastillas = 0
        tara_total = 0.0
        bruto_total = 0.0

        if pesos_texto:
            try:
                partes = [x.strip() for x in pesos_texto.split(",") if x.strip() != ""]
                for p in partes:
                    if "*" in p:
                        subparts = p.split("*")
                        peso_grupo = float(subparts[0].strip())
                        cant_canastillas = int(subparts[1].strip())
                        
                        bruto_total += peso_grupo
                        conteo_canastillas += cant_canastillas
                    else:
                        peso_individual = float(p)
                        bruto_total += peso_individual
                        conteo_canastillas += 1
                
                tara_total = conteo_canastillas * peso_tara
                cantidad_final_calculada = max(0.0, bruto_total - tara_total)
                
                st.info(f"📋 **Resumen de Báscula:** {conteo_canastillas} canastillas en total | Total Bruto: {bruto_total:.2f} Kg | Tara Total Restada ({conteo_canastillas} x {peso_tara}kg): {tara_total:.2f} Kg | **Peso Neto Real: {cantidad_final_calculada:.2f} Kg**")
            except Exception as e:
                st.error("⚠️ Error en el formato de pesos. Recuerda usar el formato correcto (ej: 23, 110*5, 45*2).")

        st.markdown("---")
        st.subheader("Datos de Recepción Físicos")
        
        if 'ultimo_registro' not in st.session_state:
            st.session_state.ultimo_registro = None

        with st.form("form_bodega", clear_on_submit=False):
            col1, col2 = st.columns(2)
            with col1:
                fecha_ingreso = st.date_input("FECHA de Ingreso")
                factura_ds = st.text_input("FACT. - DS (Número de Factura / Documento Soporte)")
                ingreso_bodega = st.number_input("INGR A BODEGA (Kg Netos)", min_value=0.0, value=float(cantidad_final_calculada), step=0.1)
                precio_final = st.number_input("PREC. FINAL por Kg ($)", min_value=0.0, value=float(fila_seleccionada['precio_pactado']), step=50.0)
            with col2:
                conductor = st.text_input("Nombre Conductor - Encargado")
                
                detalle_observacion = ""
                if conteo_canastillas > 0:
                    detalle_observacion = f"Ingreso registrado mediante {conteo_canastillas} canastillas (tara unitaria: {peso_tara} Kg). Peso Bruto total: {bruto_total:.2f} Kg."
                
                observaciones = st.text_area("OBSERVACIONES (Novedades de calidad, etc.)", value=detalle_observacion)
                
            submitted_bodega = st.form_submit_button("Registrar Entrada a Bodega")
            if submitted_bodega:
                if ingreso_bodega > 0 and precio_final > 0:
                    conn = sqlite3.connect("compras_oranges.db")
                    c = conn.cursor()
                    c.execute("""
                        INSERT INTO ingresos_bodega (fecha_ingreso, factura_ds, id_semana_ref, fruta, proveedor, cantidad_pactada, precio_pactado, ingreso_bodega, precio_final, conductor, observaciones)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (fecha_ingreso, factura_ds, fila_seleccionada['id_semana'], fila_seleccionada['fruta'], fila_seleccionada['proveedor'], fila_seleccionada['cantidad_pactada'], fila_seleccionada['precio_pactado'], ingreso_bodega, precio_final, conductor, observaciones))
                    conn.commit()
                    conn.close()
                    
                    st.session_state.ultimo_registro = {
                        "Fecha": str(fecha_ingreso),
                        "Factura_DS": factura_ds,
                        "Proveedor": fila_seleccionada['proveedor'],
                        "Fruta": fila_seleccionada['fruta'],
                        "Canastillas": conteo_canastillas,
                        "Peso_Bruto": bruto_total,
                        "Tara_Restada": tara_total,
                        "Peso_Neto_Entregado": ingreso_bodega,
                        "Precio_Kg": precio_final,
                        "Total_Pagar": ingreso_bodega * precio_final,
                        "Conductor": conductor,
                        "Observaciones": observaciones
                    }
                    st.success("✅ Ingreso de bodega registrado de forma segura.")
                else:
                    st.error("⚠️ La cantidad ingresada y el precio deben ser mayores a cero.")

        # SECCIÓN DE EXPORTACIÓN CON NUEVA OPCIÓN DE PDF PROFESIONAL
        if st.session_state.ultimo_registro:
            st.markdown("---")
            st.subheader("📩 Soportes de Entrega para el Proveedor")
            reg = st.session_state.ultimo_registro
            
            col_d1, col_d2 = st.columns(2)
            
            with col_d1:
                st.markdown("### 📄 Recibo Oficial de Entrada (PDF)")
                st.write(f"**Proveedor:** {reg['Proveedor']}")
                st.write(f"**Fruta:** {reg['Fruta']}")
                st.write(f"**Peso Neto Recibido:** {reg['Peso_Neto_Entregado']:.2f} Kg")
                st.write(f"**Total a Liquidar:** $ {reg['Total_Pagar']:,.2f}")
                
                # Generamos el archivo binario del PDF en tiempo real
                pdf_data = exportar_recibo_pdf(reg)
                
                # Botón elegante de descarga de PDF
                st.download_button(
                    label="📄 Descargar Soporte de Báscula (PDF)",
                    data=pdf_data,
                    file_name=f"Soporte_Bascula_{reg['Proveedor']}_{reg['Fruta']}_{reg['Fecha']}.pdf",
                    mime="application/pdf"
                )
                
            with col_d2:
                st.markdown("### 💬 Copiar Detalle para WhatsApp")
                
                doc_soporte = reg['Factura_DS'] if reg['Factura_DS'] else 'N/A'
                cond_nom = reg['Conductor'] if reg['Conductor'] else 'N/A'
                
                texto_whatsapp = (
                    f"*🍊 THE ORANGES - SOPORTE DE BODEGA*\n"
                    f"------------------------------------------------\n"
                    f"*Fecha:* {reg['Fecha']}\n"
                    f"*Proveedor:* {reg['Proveedor']}\n"
                    f"*Fruta:* {reg['Fruta']}\n"
                    f"------------------------------------------------\n"
                    f"*Detalle Físico de Báscula:*\n"
                    f"• Canastillas pesadas: {reg['Canastillas']} und\n"
                    f"• Peso Bruto Total: {reg['Peso_Bruto']:.2f} Kg\n"
                    f"• Tara restada (canastillas): {reg['Tara_Restada']:.2f} Kg\n"
                    f"• *PESO NETO RECIBIDO:* *{reg['Peso_Neto_Entregado']:.2f} Kg*\n"
                    f"------------------------------------------------\n"
                    f"*Precio final pactado:* $ {reg['Precio_Kg']:,.2f} / Kg\n"
                    f"*TOTAL LIQUIDACIÓN:* *${reg['Total_Pagar']:,.2f}*\n"
                    f"------------------------------------------------\n"
                    f"*Factura/Documento:* {doc_soporte}\n"
                    f"*Conductor:* {cond_nom}\n"
                    f"*Observaciones:* {reg['Observaciones']}\n\n"
                    f"_Soporte digital generado para control de entregas de The Oranges._"
                )
                
                st.text_area("Copia este texto para WhatsApp:", value=texto_whatsapp, height=180)
                st.caption("💡 Tip: Haz un clic dentro de la caja de arriba, presiona Ctrl+A, luego Ctrl+C y pégalo directamente en WhatsApp.")

# ----------------- PESTAÑA 3: CONCILIACIÓN (CONTABILIDAD) -----------------
with tab3:
    st.header("📊 Conciliación para Contabilidad (Felipe Barrios)")
    
    conn = sqlite3.connect("compras_oranges.db")
    df_ingresos = pd.read_sql_query("SELECT id_ingreso, fecha_ingreso as fecha, factura_ds as documento, id_semana_ref, fruta, proveedor, cantidad_pactada as cant_pactada, precio_pactado as prec_pactado, ingreso_bodega as ingr_bodega, precio_final as prec_final, (ingreso_bodega * precio_final) as total_pagar, conductor, observaciones FROM ingresos_bodega", conn)
    conn.close()
    
    if df_ingresos.empty:
        st.info("Aún no se han registrado ingresos en bodega para conciliar.")
    else:
        st.subheader("Registro Histórico de Ingresos Reales")
        st.dataframe(df_ingresos, use_container_width=True)
        
        st.subheader("Resumen de Desviaciones de la Semana")
        df_ingresos['merma_kg'] = df_ingresos['cant_pactada'] - df_ingresos['ingr_bodega']
        df_ingresos['desviacion_precio'] = df_ingresos['prec_final'] - df_ingresos['prec_pactado']
        
        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            total_pagos_reales = df_ingresos['total_pagar'].sum()
            st.metric("Total a Pagar Acumulado", f"$ {total_pagos_reales:,.2f}")
        with col_m2:
            total_mermas = df_ingresos['merma_kg'].sum()
            st.metric("Total Merma Consolidada (Kg)", f"{total_mermas:,.2f} Kg")
        with col_m3:
            diferencias_tarifa = (df_ingresos['desviacion_precio'] * df_ingresos['ingr_bodega']).sum()
            st.metric("Desviación en Tarifas Pactadas", f"$ {diferencias_tarifa:,.2f}", delta_color="inverse")