import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="The Oranges - Control de Compras", layout="wide")
st.title("🍊 Sistema de Control de Compras y Bodega")

def init_db():
    conn = sqlite3.connect("compras_oranges.db")
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS programacion_semanal (
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

LISTA_FRUTAS = [
    "CHULUPA", "FRESA", "GUANABANA", "GUAYABA", "LIMON", 
    "LULO", "MANGO", "MARACUYA", "MORA", "NARANJA", 
    "PIÑA", "TOMATE ARBOL", "UVA"
]

tab1, tab2, tab3 = st.tabs(["📋 Planeación Semanal (Compras)", "🚛 Recepción de Fruta (Bodega)", "📊 Control y Conciliación (Contabilidad)"])

# ----------------- PESTAÑA 1: PLANEACIÓN SEMANAL -----------------
with tab1:
    st.header("Programación de Compra Semanal")
    with st.form("form_planeacion", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            id_semana = st.text_input("ID de la Semana (Ej: SEM-2026-29)", placeholder="SEM-YYYY-WW")
            fruta = st.selectbox("Fruta a Programar", LISTA_FRUTAS)
        with col2:
            fecha_inicio = st.date_input("Fecha Inicio de Semana")
            proveedor = st.text_input("Nombre del Proveedor")
        with col3:
            fecha_fin = st.date_input("Fecha Fin de Semana")
            cantidad_pactada = st.number_input("Cantidad Pactada (Kg)", min_value=0.0, step=10.0)
            precio_pactado = st.number_input("Precio Pactado por Kg ($)", min_value=0.0, step=50.0)
            
        submitted = st.form_submit_button("Guardar Programación")
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
                st.success(f"✅ Programación para {fruta} registrada exitosamente.")
            else:
                st.error("⚠️ Por favor completa todos los campos con valores válidos.")

    st.subheader("Planeaciones Registradas")
    conn = sqlite3.connect("compras_oranges.db")
    df_plan = pd.read_sql_query("SELECT id_semana, fecha_inicio, fecha_fin, fruta, proveedor, cantidad_pactada, precio_pactado, (cantidad_pactada * precio_pactado) as total_proyectado FROM programacion_semanal", conn)
    conn.close()
    if not df_plan.empty:
        st.dataframe(df_plan, use_container_width=True)

# ----------------- PESTAÑA 2: RECEPCIÓN DE BODEGA -----------------
with tab2:
    st.header("Registro de Ingresos a Bodega")
    
    conn = sqlite3.connect("compras_oranges.db")
    df_plan_ref = pd.read_sql_query("SELECT DISTINCT id_semana, fruta, proveedor, cantidad_pactada, precio_pactado FROM programacion_semanal", conn)
    conn.close()
    
    if df_plan_ref.empty:
        st.warning("⚠️ No hay programaciones semanales registradas en el sistema. Luis debe ingresar la planeación antes de recibir fruta.")
    else:
        opciones_ref = df_plan_ref.apply(lambda r: f"{r['id_semana']} | {r['fruta']} - {r['proveedor']}", axis=1).tolist()
        seleccion = st.selectbox("Selecciona la Programación Semanal de Referencia", opciones_ref)
        
        fila_seleccionada = df_plan_ref.iloc[opciones_ref.index(seleccion)]
        
        with st.form("form_bodega", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                fecha_ingreso = st.date_input("Fecha de Ingreso a Bodega")
                factura_ds = st.text_input("Número de Factura / Documento Soporte (Fact. - DS)")
                ingreso_bodega = st.number_input("Cantidad Real Ingresada a Bodega (Kg)", min_value=0.0, step=10.0)
                precio_final = st.number_input("Precio Final Cobrado por Kg ($)", min_value=0.0, value=float(fila_seleccionada['precio_pactado']), step=50.0)
            with col2:
                conductor = st.text_input("Nombre de Conductor / Encargado")
                observaciones = st.text_area("Observaciones o Novedades de la Fruta")
                
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
                    st.success("✅ Ingreso de bodega registrado de forma segura.")
                else:
                    st.error("⚠️ La cantidad ingresada y el precio deben ser mayores a cero.")

# ----------------- PESTAÑA 3: CONCILIACIÓN (CONTABILIDAD) -----------------
with tab3:
    st.header("Conciliación para Contabilidad")
    
    conn = sqlite3.connect("compras_oranges.db")
    df_ingresos = pd.read_sql_query("SELECT fecha_ingreso, factura_ds, id_semana_ref, fruta, proveedor, cantidad_pactada, precio_pactado, ingreso_bodega, precio_final, (ingreso_bodega * precio_final) as total_pagar, conductor, observaciones FROM ingresos_bodega", conn)
    conn.close()
    
    if df_ingresos.empty:
        st.info("Aún no se han registrado ingresos en bodega para conciliar.")
    else:
        st.subheader("Registro Histórico de Ingresos Reales")
        st.dataframe(df_ingresos, use_container_width=True)
        
        st.subheader("Resumen de Desviaciones de la Semana")
        df_ingresos['merma_kg'] = df_ingresos['cantidad_pactada'] - df_ingresos['ingreso_bodega']
        df_ingresos['desviacion_precio'] = df_ingresos['precio_final'] - df_ingresos['precio_pactado']
        
        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            total_pagos_reales = df_ingresos['total_pagar'].sum()
            st.metric("Total a Pagar Acumulado", f"$ {total_pagos_reales:,.2f}")
        with col_m2:
            total_mermas = df_ingresos['merma_kg'].sum()
            st.metric("Total Merma Consolidada (Kg)", f"{total_mermas:,.2f} Kg")
        with col_m3:
            diferencias_tarifa = (df_ingresos['desviacion_precio'] * df_ingresos['ingreso_bodega']).sum()
            st.metric("Desviación en Tarifas Pactadas", f"$ {diferencias_tarifa:,.2f}", delta_color="inverse")