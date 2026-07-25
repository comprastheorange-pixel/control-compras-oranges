import streamlit as st
import sqlite3
import pandas as pd
import re
from datetime import datetime, date

# -----------------------------------------------------------------------------
# 1. CONFIGURACIÓN INICIAL DE LA APLICACIÓN
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Streamlit - The Oranges - Control de Compras y Bodega",
    page_icon="🍊",
    layout="wide"
)

# -----------------------------------------------------------------------------
# 2. BASE DE DATOS Y FUNCIONES HELPER
# -----------------------------------------------------------------------------
def init_db():
    """Crea las tablas en SQLite si no existen."""
    conn = sqlite3.connect("compras_oranges.db")
    c = conn.cursor()
    
    # Tabla para la Planeación Semanal (Órdenes de Compra)
    c.execute("""
    CREATE TABLE IF NOT EXISTS ordenes_compra (
        id_orden INTEGER PRIMARY KEY AUTOINCREMENT,
        id_semana TEXT NOT NULL,
        proveedor TEXT NOT NULL,
        vigencia_desde DATE NOT NULL,
        vigencia_hasta DATE NOT NULL,
        fruta TEXT NOT NULL,
        modalidad_precio TEXT NOT NULL,
        cantidad_kg REAL NOT NULL,
        precio_pactado REAL NOT NULL
    )
    """)
    
    # Tabla para los Ingresos a Bodega (Recepción)
    c.execute("""
    CREATE TABLE IF NOT EXISTS ingresos_bodega (
        id_ingreso INTEGER PRIMARY KEY AUTOINCREMENT,
        id_orden_ref INTEGER,
        proveedor TEXT NOT NULL,
        fecha_hora TEXT NOT NULL,
        factura_ds TEXT NOT NULL,
        conductor TEXT,
        cant_canastillas INTEGER,
        peso_bruto REAL,
        peso_tara REAL,
        peso_neto REAL,
        FOREIGN KEY (id_orden_ref) REFERENCES ordenes_compra(id_orden)
    )
    """)
    
    conn.commit()
    conn.close()

init_db()

def generar_siguiente_remision():
    """Consulta la BD y autogenera 'Remision 001', 'Remision 002', etc."""
    try:
        conn = sqlite3.connect("compras_oranges.db")
        c = conn.cursor()
        c.execute("SELECT factura_ds FROM ingresos_bodega ORDER BY id_ingreso DESC LIMIT 1")
        ultimo = c.fetchone()
        conn.close()

        if ultimo and ultimo[0]:
            numeros = re.findall(r'\d+', ultimo[0])
            if numeros:
                siguiente = int(numeros[-1]) + 1
                return f"Remision {siguiente:03d}"
    except Exception:
        pass
            
    return "Remision 001"

# Catálogo estándar de frutas
LISTA_FRUTAS = [
    "CHULUPA", "FRESA", "GUANABANA", "GUAYABA", "LIMON",
    "LULO", "MANGO", "MARACUYA", "MORA", "NARANJA",
    "PIÑA", "TOMATE ARBOL", "UVA"
]

# -----------------------------------------------------------------------------
# 3. NAVEGACIÓN Y PESTAÑAS PRINCIPALES
# -----------------------------------------------------------------------------
st.title("🍊 Streamlit - The Oranges - Control de Compras y Bodega")

tab1, tab2, tab3 = st.tabs([
    "📄 Planeación Semanal (Orden de Compra Multi-Fruta y Calidades)",
    "🚚 Recepción de Fruta y Báscula (Bodega)",
    "📈 Dashboard y Gestión de Costos"
])

# -----------------------------------------------------------------------------
# PESTAÑA 1: PLANEACIÓN SEMANAL
# -----------------------------------------------------------------------------
with tab1:
    st.header("📄 Formato Orden de Compra Semanal")
    
    with st.form("form_orden_compra", clear_on_submit=True):
        col_oc1, col_oc2, col_oc3 = st.columns(3)
        
        with col_oc1:
            id_semana = st.text_input("ID de la Semana (Ej: SEM-2026-30)", value="SEM-2026-30")
        with col_oc2:
            proveedor = st.text_input("Nombre del Proveedor", placeholder="ALIRIO")
        with col_oc3:
            vigencia_desde = st.date_input("Vigencia Desde", value=date.today())
            vigencia_hasta = st.date_input("Vigencia Hasta", value=date.today())
            
        st.markdown("---")
        st.subheader("🍇 Frutas a Programar en la Orden de Compra")
        
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            fruta_sel = st.selectbox("Selecciona Fruta #1", LISTA_FRUTAS, index=12) # UVA por defecto
            cant_kg = st.number_input("Cantidad Total (Kg)", min_value=0.0, step=10.0)
            
        with col_f2:
            modalidad = st.radio(
                f"Modalidad de precio para {fruta_sel}:",
                ["Precio Único / Global", "Desglosado por Calidad"],
                horizontal=True
            )
            precio_pactado = st.number_input("Precio Pactado/Kg ($)", min_value=0.0, step=50.0)
            
        st.markdown(f"**Subtotal Fruta:** ${cant_kg * precio_pactado:,.2f}")
        
        guardar_oc = st.form_submit_button("Guardar Orden de Compra")
        
        if guardar_oc:
            if proveedor and cant_kg > 0 and precio_pactado > 0:
                conn = sqlite3.connect("compras_oranges.db")
                c = conn.cursor()
                c.execute("""
                    INSERT INTO ordenes_compra 
                    (id_semana, proveedor, vigencia_desde, vigencia_hasta, fruta, modalidad_precio, cantidad_kg, precio_pactado)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (id_semana, proveedor, vigencia_desde, vigencia_hasta, fruta_sel, modalidad, cant_kg, precio_pactado))
                conn.commit()
                conn.close()
                st.success(f"✅ Orden de Compra guardada con éxito para {proveedor}.")
                st.rerun()
            else:
                st.error("⚠️ Ingrese el proveedor, la cantidad y un precio válido.")

    st.markdown("---")
    st.subheader("Órdenes de Compra Programadas")
    try:
        conn = sqlite3.connect("compras_oranges.db")
        df_plan = pd.read_sql_query("""
            SELECT id_orden as 'ID OC', id_semana as 'Semana', proveedor as 'Proveedor', 
                   fruta as 'Fruta', cantidad_kg as 'Kg Pactados', precio_pactado as 'Precio/Kg ($)',
                   (cantidad_kg * precio_pactado) as 'Total Proyectado ($)'
            FROM ordenes_compra
        """, conn)
        conn.close()
        if not df_plan.empty:
            st.dataframe(df_plan, use_container_width=True)
        else:
            st.info("No hay Órdenes de Compra registradas aún.")
    except Exception:
        st.info("No hay Órdenes de Compra registradas aún.")

# -----------------------------------------------------------------------------
# PESTAÑA 2: RECEPCIÓN Y BÁSCULA (BODEGA)
# -----------------------------------------------------------------------------
with tab2:
    st.header("🚚 Recepción de Fruta en Bodega (Vinculada a Orden de Compra)")
    
    df_ocs = pd.DataFrame()
    try:
        conn = sqlite3.connect("compras_oranges.db")
        df_ocs = pd.read_sql_query("SELECT id_orden, id_semana, proveedor, fruta FROM ordenes_compra", conn)
        conn.close()
    except Exception:
        pass
    
    if df_ocs.empty:
        st.warning("⚠️ No hay Órdenes de Compra registradas. Crea una en la pestaña de Planeación Semanal.")
    else:
        opciones_oc = df_ocs.apply(
            lambda r: f"OC #{r['id_orden']:04d} | {r['id_semana']} - Proveedor: {r['proveedor']} ({r['fruta']})", axis=1
        ).tolist()
        
        oc_seleccionada = st.selectbox("Selecciona la Orden de Compra Vinculada para la Recepción:", opciones_oc)
        idx_sel = opciones_oc.index(oc_seleccionada)
        oc_datos = df_ocs.iloc[idx_sel]
        
        st.markdown("---")
        
        col_rec1, col_rec2, col_rec3 = st.columns(3)
        with col_rec1:
            st.text_input("Proveedor", value=oc_datos['proveedor'], disabled=True)
        with col_rec2:
            fecha_hora_str = datetime.now().strftime("%Y/%m/%d, %H:%M")
            fecha_hora = st.text_input("Fecha y Hora", value=fecha_hora_str, disabled=True)
        with col_rec3:
            # AUTOMATIZACIÓN DEL CAMPO REMISIÓN / DS
            remision_auto = generar_siguiente_remision()
            factura_ds = st.text_input(
                "N° Factura / DS / Remisión", 
                value=remision_auto,
                placeholder="Ej: DS-104",
                help="Sugerido automáticamente. Puedes cambiarlo si el proveedor trae una factura externa o DS físico."
            )
            
        conductor = st.text_input("Conductor / Placa Vehículo", placeholder="Ej: ABC-123")
        
        st.markdown("---")
        st.subheader("🧺 Calculadora de Pesaje por Canastillas (Báscula)")
        
        col_bas1, col_bas2 = st.columns([1, 3])
        with col_bas1:
            peso_tara_unitario = st.number_input("Peso Tara por Canastilla (Kg)", value=2.00, step=0.10)
        with col_bas2:
            formula_pesos = st.text_area(
                "Pesos de Canastillas", 
                value="111.85*5,116.45*5,109*5,111.75*5,111.80*5,108.40*5,109.70*5,72.75*3,38.25*2",
                help="Formato: peso*cantidad separados por coma."
            )
        
        # Procesamiento dinámico de la cadena de pesaje
        peso_bruto_total = 0.0
        total_canastillas = 0
        try:
            items = formula_pesos.replace(" ", "").split(",")
            for item in items:
                if "*" in item:
                    peso, cant = item.split("*")
                    peso_bruto_total += float(peso) * float(cant)
                    total_canastillas += int(cant)
                elif item:
                    peso_bruto_total += float(item)
                    total_canastillas += 1
        except Exception:
            st.warning("⚠️ Revisa la sintaxis introducida en la casilla de peso por canastillas.")

        peso_tara_total = total_canastillas * peso_tara_unitario
        peso_neto_total = max(0.0, peso_bruto_total - peso_tara_total)
        
        st.info(
            f"📑 **Báscula:** {total_canastillas} canastillas | "
            f"**Bruto:** {peso_bruto_total:,.2f} Kg | "
            f"**Tara:** -{peso_tara_total:,.2f} Kg | "
            f"**Neto:** {peso_neto_total:,.2f} Kg"
        )
        
        if st.button("📥 Registrar Entrada a Bodega", type="primary"):
            conn = sqlite3.connect("compras_oranges.db")
            c = conn.cursor()
            c.execute("""
                INSERT INTO ingresos_bodega 
                (id_orden_ref, proveedor, fecha_hora, factura_ds, conductor, cant_canastillas, peso_bruto, peso_tara, peso_neto)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (int(oc_datos['id_orden']), oc_datos['proveedor'], fecha_hora, factura_ds, conductor, total_canastillas, peso_bruto_total, peso_tara_total, peso_neto_total))
            conn.commit()
            conn.close()
            st.success(f"✅ Recepción registrada correctamente bajo la remisión/factura '{factura_ds}'.")
            st.rerun()

# -----------------------------------------------------------------------------
# PESTAÑA 3: DASHBOARD Y GESTIÓN DE COSTOS
# -----------------------------------------------------------------------------
with tab3:
    st.header("📈 Dashboard y Gestión de Costos")
    
    has_data = False
    try:
        conn = sqlite3.connect("compras_oranges.db")
        c = conn.cursor()
        c.execute("SELECT count(*) FROM ingresos_bodega")
        if c.fetchone()[0] > 0:
            has_data = True
        conn.close()
    except Exception:
        has_data = False
        
    if not has_data:
        st.info("ℹ️ Aún no se han registrado ingresos en bodega.")
    else:
        try:
            conn = sqlite3.connect("compras_oranges.db")
            df_recepciones = pd.read_sql_query("""
                SELECT ib.id_ingreso as 'ID Ingreso', ib.factura_ds as 'Factura/Remisión', 
                       ib.fecha_hora as 'Fecha/Hora', ib.proveedor as 'Proveedor', oc.fruta as 'Fruta',
                       ib.peso_neto as 'Peso Neto (Kg)', oc.precio_pactado as 'Precio Pactado ($)',
                       (ib.peso_neto * oc.precio_pactado) as 'Total Valor ($)'
                FROM ingresos_bodega ib
                JOIN ordenes_compra oc ON ib.id_orden_ref = oc.id_orden
            """, conn)
            conn.close()

            if df_recepciones.empty:
                st.info("ℹ️ Aún no hay recepciones registradas en bodega.")
            else:
                m1, m2, m3 = st.columns(3)
                m1.metric("Total Recepciones", len(df_recepciones))
                m2.metric("Volumen Total Neto (Kg)", f"{df_recepciones['Peso Neto (Kg)'].sum():,.2f} Kg")
                m3.metric("Costo Total Fruta ($)", f"${df_recepciones['Total Valor ($)'].sum():,.2f}")
                
                st.markdown("---")
                st.subheader("Histórico de Entradas a Bodega")
                st.dataframe(df_recepciones, use_container_width=True)
        except Exception:
            st.info("ℹ️ Ocurrió un inconveniente al cargar los datos. Registre una nueva orden y entrada para sincronizar.")