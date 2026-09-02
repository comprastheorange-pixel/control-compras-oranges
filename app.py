import streamlit as st
import pandas as pd
from datetime import datetime
import sqlite3
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
import io

# ---------------------------------------------------------
# CONFIGURACIÓN DE LA BASE DE DATOS
# ---------------------------------------------------------
def inicializar_bd():
    conn = sqlite3.connect("bascula_the_oranges.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tiquetes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            consecutivo TEXT,
            fecha TEXT,
            proveedor TEXT,
            factura TEXT,
            fruta TEXT,
            calidad TEXT,
            conductor TEXT,
            tara_canastilla REAL,
            total_canastillas INTEGER,
            peso_bruto_total REAL,
            peso_tara_total REAL,
            peso_neto REAL
        )
    ''')
    conn.commit()
    return conn

conn = inicializar_bd()

# Configuración de página de Streamlit
st.set_page_config(
    page_title="Tiquete de Báscula - The Oranges",
    layout="wide",
    page_icon="🍊"
)

st.title("🍊 Sistema de Control de Báscula y Recepción de Fruta")
st.write("Registra el peso bruto por tandas de canastillas, calcula automáticamente el neto y genera el tiquete oficial en PDF.")

# Menú lateral
menu = st.sidebar.selectbox("Menú Principal", ["⚖️ Registrar Entrada de Fruta", "📊 Historial de Tiquetes"])

# ---------------------------------------------------------
# MÓDULO 1: REGISTRAR ENTRADA DE FRUTA
# ---------------------------------------------------------
if menu == "⚖️ Registrar Entrada de Fruta":
    
    st.subheader("1. Información del Proveedor y Carga")
    
    # Generar un consecutivo temporal para el tiquete
    if 'consecutivo_actual' not in st.session_state:
        st.session_state.consecutivo_actual = f"TQ-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    col1, col2 = st.columns(2)
    with col1:
        proveedor = st.text_input("Nombre del Proveedor / Finca", placeholder="Ej: Finca El Paraíso")
        factura = st.text_input("Número de Factura / Doc. Soporte", placeholder="Ej: DS-1024")
        tara_canastilla = st.number_input("Tara estándar por canastilla vacía (Kg)", min_value=0.0, value=1.5, step=0.1)
    
    with col2:
        # Opciones de fruta
        opciones_fruta = ["MARACUYA", "MANGO", "MORA", "LULO", "GUANABANA", "LIMON", "NARANJA", "PIÑA", "PULPA DE FRUTA", "OTRA"]
        
        fruta_seleccionada = st.selectbox(
            "Fruta que Ingresa", 
            opciones_fruta,
            key="selectbox_fruta"
        )
        
        # Si selecciona OTRA, mostramos el campo de texto interactivo
        if fruta_seleccionada == "OTRA":
            fruta_custom = st.text_input("Escribe el nombre de la otra fruta", placeholder="Ej: FEIJOA", key="input_otra_fruta")
            fruta = fruta_custom.strip().upper() if fruta_custom else "OTRA (Sin especificar)"
        else:
            fruta = fruta_seleccionada

        calidad = st.selectbox("Calidad", ["Primera", "Segunda", "Industrial / Descarte"])
        conductor = st.text_input("Nombre del Conductor / Entregador", placeholder="Ej: Carlos Mendoza")

    st.divider()
    st.subheader("2. Registrar Tanda en la Báscula")

    # Inicializar lista temporal de tandas en session_state si no existe
    if 'tandas_actuales' not in st.session_state:
        st.session_state.tandas_actuales = []

    col_t1, col_t2 = st.columns(2)
    with col_t1:
        cant_canastillas = st.number_input("Cantidad de canastillas en esta tanda", min_value=1, value=5, step=1, key="cant_canas")
    with col_t2:
        peso_bruto_tanda = st.number_input("Peso Bruto marcado en la báscula (Kg)", min_value=0.0, value=100.0, step=0.5, key="peso_bruto")

    if st.button("➕ Guardar y Registrar Tanda", use_container_width=True):
        st.session_state.tandas_actuales.append({
            "canastillas": cant_canastillas,
            "peso_bruto": peso_bruto_tanda
        })
        st.success(f"Tanda agregada: {cant_canastillas} canastillas | Bruto: {peso_bruto_tanda:,.2f} Kg")

    # Mostrar tabla de tandas acumuladas
    if st.session_state.tandas_actuales:
        st.markdown("#### Tandas Registradas para este Ingreso:")
        df_tandas = pd.DataFrame(st.session_state.tandas_actuales)
        df_tandas.columns = ["Cantidad Canastillas", "Peso Bruto (Kg)"]
        st.dataframe(df_tandas, use_container_width=True)

        total_c = df_tandas["Cantidad Canastillas"].sum()
        total_b = df_tandas["Peso Bruto (Kg)"].sum()
        total_tara = total_c * tara_canastilla
        total_neto = total_b - total_tara

        st.markdown("### Resumen de Pesaje")
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.metric("Total Canastillas", f"{total_c}")
        with m2:
            st.metric("Peso Bruto Acumulado", f"{total_b:,.2f} Kg")
        with m3:
            st.metric("Total Tara (Canastillas)", f"{total_tara:,.2f} Kg")
        with m4:
            st.metric("PESO NETO DE FRUTA", f"{total_neto:,.2f} Kg", delta="¡Listo para liquidar!")

        st.divider()

        # Botón para guardar en la base de datos definitiva
        if st.button("💾 Finalizar y Guardar Tiquete Oficial", type="primary", use_container_width=True):
            if not proveedor:
                st.error("⚠️ Por favor ingresa el nombre del proveedor.")
            else:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO tiquetes (consecutivo, fecha, proveedor, factura, fruta, calidad, conductor, tara_canastilla, total_canastillas, peso_bruto_total, peso_tara_total, peso_neto)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (st.session_state.consecutivo_actual, str(datetime.now()), proveedor, factura, fruta, calidad, conductor, tara_canastilla, int(total_c), float(total_b), float(total_tara), float(total_neto)))
                conn.commit()
                st.success(f"¡Tiquete {st.session_state.consecutivo_actual} guardado con éxito en la base de datos!")
                
                # Generador de PDF del Tiquete
                def generar_pdf_tiquete():
                    buffer = io.BytesIO()
                    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
                    elements = []
                    
                    styles = getSampleStyleSheet()
                    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=16, textColor=colors.HexColor('#1B4D3E'), alignment=1, spaceAfter=4)
                    subtitle_style = ParagraphStyle('SubtitleStyle', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#555555'), alignment=1, spaceAfter=15)
                    bold_text = ParagraphStyle('BoldText', parent=styles['Normal'], fontSize=9, fontName='Helvetica-Bold')
                    regular_text = ParagraphStyle('RegularText', parent=styles['Normal'], fontSize=9)

                    elements.append(Paragraph("THE ORANGES S.A.S.", title_style))
                    elements.append(Paragraph("Planta de Procesamiento de Fruta — TIQUETE DE BÁSCULA", subtitle_style))
                    
                    data_info = [
                        [Paragraph("No. Tiquete:", bold_text), Paragraph(st.session_state.consecutivo_actual, regular_text),
                         Paragraph("Fecha:", bold_text), Paragraph(datetime.now().strftime('%Y-%m-%d %H:%M'), regular_text)],
                        [Paragraph("Proveedor:", bold_text), Paragraph(proveedor, regular_text),
                         Paragraph("Factura / Soporte:", bold_text), Paragraph(factura or 'N/A', regular_text)],
                        [Paragraph("Fruta:", bold_text), Paragraph(fruta, regular_text),
                         Paragraph("Calidad:", bold_text), Paragraph(calidad, regular_text)],
                        [Paragraph("Conductor:", bold_text), Paragraph(conductor or 'N/A', regular_text),
                         Paragraph("Tara Canastilla:", bold_text), Paragraph(f"{tara_canastilla} Kg", regular_text)]
                    ]
                    
                    t_info = Table(data_info, colWidths=[90, 180, 90, 180])
                    t_info.setStyle(TableStyle([
                        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F9F9F9')),
                        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#DCDCDC')),
                        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                        ('PADDING', (0,0), (-1,-1), 5),
                    ]))
                    elements.append(t_info)
                    elements.append(Spacer(1, 15))
                    
                    # Tabla resumen de pesos
                    totales_data = [
                        ["Concepto", "Valor Medida"],
                        ["Cantidad Total de Canastillas", f"{int(total_c)} un."],
                        ["Peso Bruto Total", f"{total_b:,.2f} Kg"],
                        ["Total Tara Canastillas", f"{total_tara:,.2f} Kg"],
                        ["PESO NETO DE FRUTA", f"{total_neto:,.2f} Kg"]
                    ]
                    t_totales = Table(totales_data, colWidths=[340, 200])
                    t_totales.setStyle(TableStyle([
                        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1B4D3E')),
                        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0,0), (-1,0), 9),
                        ('BACKGROUND', (0,1), (-1,-2), colors.HexColor('#FCFCFC')),
                        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#E8F5E9')),
                        ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
                        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E0E0E0')),
                        ('PADDING', (0,0), (-1,-1), 6),
                    ]))
                    elements.append(t_totales)
                    
                    elements.append(Spacer(1, 50))
                    firma_data = [
                        ["____________________________________", "____________________________________"],
                        ["Báscula / Recibo The Oranges", "Firma Conductor / Proveedor"]
                    ]
                    t_firmas = Table(firma_data, colWidths=[270, 270])
                    t_firmas.setStyle(TableStyle([
                        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
                        ('FONTSIZE', (0,0), (-1,-1), 9),
                        ('TEXTCOLOR', (0,0), (-1,-1), colors.HexColor('#333333')),
                    ]))
                    elements.append(t_firmas)
                    
                    doc.build(elements)
                    buffer.seek(0)
                    return buffer.getvalue()

                pdf_bytes = generar_pdf_tiquete()
                st.download_button(
                    label="📥 Descargar Tiquete Oficial en PDF",
                    data=pdf_bytes,
                    file_name=f"Tiquete_{st.session_state.consecutivo_actual}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
                
                # Botón para limpiar y empezar nuevo registro
                if st.button("🔄 Iniciar Nuevo Tiquete"):
                    st.session_state.tandas_actuales = []
                    st.session_state.consecutivo_actual = f"TQ-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
                    st.rerun()

    else:
        st.info("💡 Ingresa las canastillas y el peso bruto de la tanda arriba y haz clic en 'Guardar y Registrar Tanda'.")

# ---------------------------------------------------------
# MÓDULO 2: HISTORIAL DE TIQUETES
# ---------------------------------------------------------
elif menu == "📊 Historial de Tiquetes":
    st.subheader("Historial de Ingresos de Fruta Registrados")
    try:
        df_hist = pd.read_sql("SELECT consecutivo as 'No. Tiquete', fecha as 'Fecha', proveedor as 'Proveedor', fruta as 'Fruta', calidad as 'Calidad', total_canastillas as 'Canastillas', peso_neto as 'Neto (Kg)' FROM tiquetes", conn)
        if not df_hist.empty:
            st.dataframe(df_hist, use_container_width=True)
        else:
            st.warning("No hay tiquetes registrados todavía.")
    except Exception as e:
        st.error(f"Error cargando el historial: {e}")