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
# CONFIGURACIÓN DE LA BASE DE DATOS SQLITE (Nube / Local)
# ---------------------------------------------------------
def inicializar_bd():
    conn = sqlite3.connect("bascula_the_oranges.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pesajes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_registro TEXT,
            proveedor TEXT,
            factura TEXT,
            fruta TEXT,
            calidad TEXT,
            conductor TEXT,
            tara_unit REAL,
            pesaje_num INTEGER,
            canastillas INTEGER,
            peso_bruto REAL,
            tara_total REAL,
            peso_neto REAL
        )
    ''')
    conn.commit()
    return conn

conn = inicializar_bd()

# Configuración de página de Streamlit
st.set_page_config(
    page_title="Tiquete de Báscula - The Oranges",
    layout="centered",
    page_icon="🍊"
)

st.title("🍊 Báscula de Recepción - Almacenamiento y Tiquete PDF")
st.write("Registra los pesajes, guárdalos de forma permanente y genera el tiquete oficial.")

# ---------------------------------------------------------
# DATOS GENERALES DEL INGRESO
# ---------------------------------------------------------
with st.container():
    st.subheader("1. Información del Proveedor y Carga")
    col1, col2 = st.columns(2)
    with col1:
        proveedor = st.text_input("Nombre del Proveedor / Finca", placeholder="Ej: Finca El Paraíso")
        factura = st.text_input("Número de Factura / Doc. Soporte", placeholder="Ej: DS-1024")
    with col2:
        fruta = st.selectbox("Fruta que Ingresa", ["MARACUYA", "MANGO", "MORA", "LULO", "GUANABANA", "LIMON", "NARANJA", "PIÑA", "OTRA"])
        calidad = st.selectbox("Calidad", ["Primera", "Segunda", "Industrial / Pulpa"])

    col3, col4 = st.columns(2)
    with col3:
        tara_unit = st.number_input("Tara estándar por canastilla vacía (Kg)", min_value=0.0, value=1.5, step=0.1)
    with col4:
        conductor = st.text_input("Nombre del Conductor / Entregador", placeholder="Ej: Carlos Mendoza")

st.divider()

# ---------------------------------------------------------
# ENTRADA DE PESAJES INDIVIDUALES (TANDAS)
# ---------------------------------------------------------
st.subheader("2. Registrar Tanda en la Báscula")

with st.form("form_agregar_pesaje", clear_on_submit=True):
    col_p1, col_p2 = st.columns(2)
    with col_p1:
        cant_canastillas = st.number_input("Cantidad de canastillas en esta tanda", min_value=1, step=1, value=5)
    with col_p2:
        peso_bruto = st.number_input("Peso Bruto marcado en la báscula (Kg)", min_value=0.1, step=0.5, value=100.0)
    
    btn_agregar = st.form_submit_button("➕ Guardar y Registrar Tanda")
    
    if btn_agregar:
        if not proveedor or not factura:
            st.error("⚠️ Por favor ingresa el nombre del Proveedor y el Número de Factura antes de registrar pesajes.")
        else:
            tara_tanda = cant_canastillas * tara_unit
            neto_tanda = peso_bruto - tara_tanda
            fecha_ahora = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Obtener el número de pesaje actual para esta factura
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM pesajes WHERE factura = ?", (factura,))
            num_actual = cursor.fetchone()[0] + 1
            
            # Guardar en la base de datos SQLite
            cursor.execute('''
                INSERT INTO pesajes (fecha_registro, proveedor, factura, fruta, calidad, conductor, tara_unit, pesaje_num, canastillas, peso_bruto, tara_total, peso_neto)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (fecha_ahora, proveedor, factura, fruta, calidad, conductor, tara_unit, num_actual, cant_canastillas, peso_bruto, tara_tanda, neto_tanda))
            conn.commit()
            
            st.success(f"✅ ¡Pesaje #{num_actual} guardado exitosamente en la base de datos!")

# Botón para limpiar o iniciar un nuevo lote
if st.button("🗑️ Limpiar Lote Actual en Pantalla"):
    st.rerun()

st.divider()

# ---------------------------------------------------------
# TABLA ACUMULADA Y TOTALES DESDE LA BASE DE DATOS
# ---------------------------------------------------------
st.subheader("3. Detalle Acumulado del Lote Actual")

if factura:
    query_lote = "SELECT pesaje_num as 'Pesaje #', canastillas as 'Canastillas', peso_bruto as 'Peso Bruto (Kg)', tara_total as 'Tara (Kg)', peso_neto as 'Peso Neto (Kg)' FROM pesajes WHERE factura = ?"
    df_pesajes = pd.read_sql(query_lote, conn, params=(factura,))
else:
    df_pesajes = pd.DataFrame()

if not df_pesajes.empty:
    st.dataframe(df_pesajes, use_container_width=True)
    
    total_canastillas = df_pesajes['Canastillas'].sum()
    total_bruto = df_pesajes['Peso Bruto (Kg)'].sum()
    total_tara = df_pesajes['Tara (Kg)'].sum()
    total_neto = df_pesajes['Peso Neto (Kg)'].sum()
    
    col_m1, col_m2, col_m3 = st.columns(3)
    with col_m1:
        st.metric("Total Canastillas", f"{total_canastillas:,} und")
    with col_m2:
        st.metric("Peso Bruto Acumulado", f"{total_bruto:,.2f} Kg")
    with col_m3:
        st.metric("⚖️ PESO NETO TOTAL FRUTA", f"{total_neto:,.2f} Kg")
        
    st.markdown("---")
    
    # ---------------------------------------------------------
    # GENERACIÓN DE PDF CON REPORTLAB
    # ---------------------------------------------------------
    def generar_pdf_tiquete():
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
        elements = []
        
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=16, textColor=colors.HexColor('#1B4D3E'), alignment=1, spaceAfter=4)
        subtitle_style = ParagraphStyle('SubtitleStyle', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#555555'), alignment=1, spaceAfter=15)
        bold_text = ParagraphStyle('BoldText', parent=styles['Normal'], fontSize=9, fontName='Helvetica-Bold')
        regular_text = ParagraphStyle('RegularText', parent=styles['Normal'], fontSize=9)

        elements.append(Paragraph("THE ORANGES", title_style))
        elements.append(Paragraph("Comercialización y Transformación de Fruta - Tiquete de Báscula", subtitle_style))
        
        data_info = [
            [Paragraph("Proveedor:", bold_text), Paragraph(proveedor or 'No especificado', regular_text),
             Paragraph("Fecha / Hora:", bold_text), Paragraph(datetime.now().strftime('%Y-%m-%d %H:%M'), regular_text)],
            [Paragraph("Factura / Doc:", bold_text), Paragraph(factura or 'N/A', regular_text),
             Paragraph("Fruta / Calidad:", bold_text), Paragraph(f"{fruta} ({calidad})", regular_text)],
            [Paragraph("Conductor:", bold_text), Paragraph(conductor or 'No especificado', regular_text),
             Paragraph("Tara Canastilla:", bold_text), Paragraph(f"{tara_unit:.2f} Kg", regular_text)]
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
        
        table_data = [["Pesaje #", "Canastillas", "Peso Bruto (Kg)", "Tara Total (Kg)", "Peso Neto Fruta (Kg)"]]
        
        for index, row in df_pesajes.iterrows():
            table_data.append([
                str(row['Pesaje #']),
                str(row['Canastillas']),
                f"{row['Peso Bruto (Kg)']:,.2f}",
                f"{row['Tara (Kg)']:,.2f}",
                f"{row['Peso Neto (Kg)']:,.2f}"
            ])
            
        table_data.append([
            "TOTALES",
            str(total_canastillas),
            f"{total_bruto:,.2f}",
            f"{total_tara:,.2f}",
            f"{total_neto:,.2f}"
        ])
        
        t_pesajes = Table(table_data, colWidths=[80, 100, 110, 110, 140])
        t_pesajes.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1B4D3E')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 9),
            ('BOTTOMPADDING', (0,0), (-1,0), 6),
            ('BACKGROUND', (0,1), (-1,-2), colors.HexColor('#FCFCFC')),
            ('GRID', (0,0), (-1,-2), 0.5, colors.HexColor('#E0E0E0')),
            ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#F0F4F1')),
            ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
            ('LINEABOVE', (0,-1), (-1,-1), 1.5, colors.HexColor('#1B4D3E')),
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#1B4D3E')),
            ('PADDING', (0,0), (-1,-1), 6),
        ]))
        elements.append(t_pesajes)
        
        elements.append(Spacer(1, 40))
        firma_data = [
            ["____________________________________", "____________________________________"],
            ["Firma Entregador / Proveedor", "Firma Báscula / Bodega"]
        ]
        t_firmas = Table(firma_data, colWidths=[250, 250])
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
        label="📥 Generar y Descargar Tiquete Oficial en PDF",
        data=pdf_bytes,
        file_name=f"Tiquete_Bascula_{factura}.pdf",
        mime="application/pdf"
    )
else:
    st.info("💡 Ingresa el número de factura y proveedor arriba, y comienza a registrar pesajes para ver el acumulado guardado.")