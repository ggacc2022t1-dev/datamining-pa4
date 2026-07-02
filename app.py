import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import subprocess
import io
import os

# Configuración de página de Streamlit
st.set_page_config(page_title="Dashboard de Hotel", layout="wide")

# Aplicar el estilo ggplot a todos los gráficos
plt.style.use('ggplot')

# -----------------------------------------------------------------------------
# 1. CARGA Y EXTRACCIÓN AUTOMÁTICA DESDE ACCESS (.accdb)
# -----------------------------------------------------------------------------
@st.cache_data
def load_and_prep_data():
    archivo_db = 'HotelInternational.accdb'
    base_de_datos = {}
    
    # Verificación de la existencia del archivo de Access
    if not os.path.exists(archivo_db):
        st.error(f"❌ No se encontró el archivo '{archivo_db}' en la carpeta raíz del proyecto.")
        st.stop()

    # Ejecución de mdb-tools mediante subprocess
    try:
        # 1. Obtener la lista de tablas en la base de datos
        resultado = subprocess.run(['mdb-tables', '-1', archivo_db], capture_output=True, text=True, check=True)
        tablas = resultado.stdout.splitlines()
        
        # 2. Leer cada tabla y cargarla en el diccionario de DataFrames
        for tabla in tablas:
            if not tabla.startswith('MSys') and tabla.strip():
                comando = ['mdb-export', archivo_db, tabla]
                res_export = subprocess.run(comando, capture_output=True, text=True)
                
                if res_export.returncode == 0:
                    df = pd.read_csv(io.StringIO(res_export.stdout))
                    base_de_datos[tabla] = df
    except FileNotFoundError:
        st.error("❌ El comando 'mdb-tables' no está disponible en este servidor. "
                 "Por favor, asegúrate de haber creado el archivo 'packages.txt' con la línea 'mdbtools'.")
        st.stop()
    except Exception as e:
        st.error(f"❌ Error crítico al extraer los datos de Access: {e}")
        st.stop()

    # 3. Recuperamos los DataFrames que ya extrajimos de Access
    df_clientes = base_de_datos.get('Clientes', pd.DataFrame())
    df_checkin = base_de_datos.get('CheckInHotel', pd.DataFrame())
    df_consumo = base_de_datos.get('ConsumoHotel', pd.DataFrame())
    
    # 4. Leemos el archivo de reservas (intenta CSV, si no, busca si está en la DB)
    try:
        df_reservas = pd.read_csv('reservas.csv')
    except FileNotFoundError:
        # Por si acaso la tabla 'reservas' también venía dentro del propio .accdb
        df_reservas = base_de_datos.get('reservas', base_de_datos.get('Reservas', pd.DataFrame()))
        if df_reservas.empty:
            st.error("❌ No se encontró el archivo 'reservas.csv' ni una tabla llamada 'reservas' dentro de Access.")
            st.stop()

    # Unificamos el nombre de la columna para que todas las tablas se conecten bien
    df_reservas.rename(columns={'id_reserva': 'ReservaID'}, inplace=True)

    # PREPARACIÓN DE DATOS (CRUCE DE TABLAS)
    df_master = pd.merge(df_reservas, df_checkin, on='ReservaID', how='left')

    # Agregamos el parámetro encoding='utf-16' para la geografía
    try:
        df_geo = pd.read_csv('Geography.txt', sep=',', encoding='utf-16')
        df_master = pd.merge(df_master, df_geo, on='GeographyKey', how='left')
    except FileNotFoundError:
        df_master['EnglishCountryRegionName'] = 'Desconocido'

    # Estandarizamos booleanos
    df_master['Llego_clean'] = df_master['Llego'].astype(str).str.strip().str.lower().isin(['1', 'true', 'sí', 'si', 'yes', '-1'])
    
    if 'cancelo_reserva' in df_master.columns:
        df_master['Cancelo_clean'] = df_master['cancelo_reserva'].astype(str).str.strip().str.lower().isin(['sí', 'si', 'yes', '1'])
    else:
        df_master['Cancelo_clean'] = False

    # Definimos "No Show": Cliente que NO canceló, pero que NO llegó al hotel
    df_master['NoShow'] = (~df_master['Cancelo_clean']) & (~df_master['Llego_clean'])
    
    return df_master, df_checkin, df_consumo

# Ejecutar la carga y extracción automática
df_master, df_checkin, df_consumo = load_and_prep_data()


# -----------------------------------------------------------------------------
# 2. INTERFAZ DEL DASHBOARD VISUAL (GGPLOT / SEABORN)
# -----------------------------------------------------------------------------
st.title("🏨 Dashboard Hotelero - Extracción Dinámica Access")
st.markdown("---")

# ================= SECCIÓN 1: KPIs PRINCIPALES =================
st.header("1. Indicadores Generales (KPIs)")
col1, col2, col3, col4 = st.columns(4)

pct_llegaron = (df_master['Llego_clean'].sum() / len(df_master)) * 100
col1.metric("Llegadas Efectivas", f"{pct_llegaron:.2f}%")

pct_no_show = (df_master['NoShow'].sum() / len(df_master)) * 100
col2.metric("Tasa de No Show", f"{pct_no_show:.2f}%")

late_mask = df_master['LateCheckIn'].astype(str).str.strip().str.lower().isin(['1', 'true', 'sí', 'si', 'yes', '-1'])
pct_late = late_mask.mean() * 100
col3.metric("Late Check-In", f"{pct_late:.2f}%")

if 'HoraLlegada' in df_checkin.columns:
    horas_validas = pd.to_datetime(df_checkin['HoraLlegada'], errors='coerce').dropna()
    hora_promedio = horas_validas.mean().strftime('%H:%M:%S') if not horas_validas.empty else "N/A"
    col4.metric("Hora Promedio Llegada", hora_promedio)

st.markdown("---")

# ================= SECCIÓN 2: ANÁLISIS DE NO SHOW =================
st.header("2. Análisis de Inasistencias (No Show)")
col1, col2 = st.columns(2)

with col1:
    st.subheader("No Show por Canal de Reserva")
    no_show_por_canal = df_master.groupby('canal_reserva')['NoShow'].mean().reset_index()
    no_show_por_canal['NoShow'] = no_show_por_canal['NoShow'] * 100
    no_show_por_canal = no_show_por_canal.sort_values('NoShow', ascending=False)
    
    fig, ax = plt.subplots(figsize=(8, 5))
    sns.barplot(data=no_show_por_canal, x='canal_reserva', y='NoShow', palette='Blues_r', ax=ax)
    ax.set_ylabel('Porcentaje de No Show (%)')
    ax.set_xlabel('Canal de Reserva')
    plt.xticks(rotation=45)
    st.pyplot(fig)

with col2:
    st.subheader("Top 5 Países con más No Show")
    if 'EnglishCountryRegionName' in df_master.columns:
        paises_no_show = df_master[df_master['NoShow'] == True]['EnglishCountryRegionName'].value_counts().head(5).reset_index()
        paises_no_show.columns = ['País', 'Cantidad']
        
        fig2, ax2 = plt.subplots(figsize=(8, 5))
        sns.barplot(data=paises_no_show, x='País', y='Cantidad', palette='Reds_r', ax=ax2)
        ax2.set_ylabel('Cantidad de Reservas')
        ax2.set_xlabel('País')
        st.pyplot(fig2)

st.markdown("---")

# ================= SECCIÓN 3: INGRESOS Y COMPORTAMIENTO =================
st.header("3. Ingresos y Comportamiento del Huésped")
col1, col2 = st.columns(2)

with col1:
    st.subheader("Ingresos por Tipo de Habitación")
    ingresos_cat = df_master.groupby('tipo_habitacion')['monto_reserva_origen'].sum().reset_index()
    ingresos_cat = ingresos_cat.sort_values('monto_reserva_origen', ascending=False)
    
    fig3, ax3 = plt.subplots(figsize=(8, 5))
    sns.barplot(data=ingresos_cat, y='tipo_habitacion', x='monto_reserva_origen', palette='Greens_r', ax=ax3)
    ax3.set_xlabel('Ingreso Total ($)')
    ax3.set_ylabel('Tipo de Habitación')
    st.pyplot(fig3)

with col2:
    st.subheader("Relación: Noches vs Gasto Total")
    gastos_adicionales = df_consumo.groupby('ReservaID')['Monto'].sum().reset_index()
    gastos_adicionales.rename(columns={'Monto': 'GastoConsumos'}, inplace=True)
    df_relacion = pd.merge(df_master[['ReservaID', 'noches', 'monto_reserva_origen']], gastos_adicionales, on='ReservaID', how='left')
    df_relacion['GastoConsumos'] = df_relacion['GastoConsumos'].fillna(0)
    df_relacion['GastoTotal'] = df_relacion['monto_reserva_origen'] + df_relacion['GastoConsumos']
    
    correlacion = df_relacion['noches'].corr(df_relacion['GastoTotal'])
    
    fig4, ax4 = plt.subplots(figsize=(8, 5))
    sns.scatterplot(data=df_relacion, x='noches', y='GastoTotal', alpha=0.6, color='purple', ax=ax4)
    sns.regplot(data=df_relacion, x='noches', y='GastoTotal', scatter=False, color='black', ax=ax4)
    ax4.set_xlabel('Cantidad de Noches')
    ax4.set_ylabel('Gasto Total ($)')
    st.pyplot(fig4)
    st.caption(f"Coeficiente de correlación de Pearson: **{correlacion:.3f}**")
