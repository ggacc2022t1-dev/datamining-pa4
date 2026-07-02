import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

# Configuración de página de Streamlit
st.set_page_config(page_title="Dashboard de Hotel", layout="wide")

# Aplicar el estilo ggplot a todos los gráficos de matplotlib/seaborn
plt.style.use('ggplot')

# -----------------------------------------------------------------------------
# 1. CARGA Y PREPARACIÓN DE DATOS (Caché para optimizar Streamlit)
# -----------------------------------------------------------------------------
@st.cache_data
def load_and_prep_data():
    # NOTA: Reemplaza esto con tu conexión real a Access / lectura de archivos
    # df_clientes = base_de_datos.get('Clientes', pd.DataFrame())
    # df_checkin = base_de_datos.get('CheckInHotel', pd.DataFrame())
    # df_consumo = base_de_datos.get('ConsumoHotel', pd.DataFrame())
    
    # Simulación para que el código no rompa (Borrar y usar tus datos reales)
    df_reservas = pd.read_csv('reservas.csv')
    df_checkin = pd.read_csv('checkin.csv') # Asumiendo que lo extraes
    df_consumo = pd.read_csv('consumo.csv') # Asumiendo que lo extraes
    
    # Limpieza básica inicial
    df_reservas.rename(columns={'id_reserva': 'ReservaID'}, inplace=True)
    
    # Cruce de tablas
    df_master = pd.merge(df_reservas, df_checkin, on='ReservaID', how='left')
    
    # Datos geográficos
    try:
        df_geo = pd.read_csv('Geography.txt', sep=',', encoding='utf-16')
        df_master = pd.merge(df_master, df_geo, on='GeographyKey', how='left')
    except FileNotFoundError:
        df_master['EnglishCountryRegionName'] = 'Desconocido'

    # Estandarizar booleanos
    df_master['Llego_clean'] = df_master['Llego'].astype(str).str.strip().str.lower().isin(['1', 'true', 'sí', 'si', 'yes', '-1'])
    if 'cancelo_reserva' in df_master.columns:
        df_master['Cancelo_clean'] = df_master['cancelo_reserva'].astype(str).str.strip().str.lower().isin(['sí', 'si', 'yes', '1'])
    else:
        df_master['Cancelo_clean'] = False

    # Definir "No Show"
    df_master['NoShow'] = (~df_master['Cancelo_clean']) & (~df_master['Llego_clean'])
    
    return df_master, df_checkin, df_consumo

# Cargar datos
try:
    df_master, df_checkin, df_consumo = load_and_prep_data()
except Exception as e:
    st.error(f"Error al cargar los datos. Asegúrate de tener los archivos CSV en la misma carpeta. Detalle: {e}")
    st.stop()


# -----------------------------------------------------------------------------
# 2. INTERFAZ DEL DASHBOARD
# -----------------------------------------------------------------------------
st.title("🏨 Dashboard de Análisis Hotelero")
st.markdown("---")

# ================= SECCIÓN 1: KPIs PRINCIPALES =================
st.header("1. Indicadores Generales (KPIs)")

col1, col2, col3, col4 = st.columns(4)

# 1. Porcentaje de llegadas
pct_llegaron = (df_master['Llego_clean'].sum() / len(df_master)) * 100
col1.metric("Llegadas Efectivas", f"{pct_llegaron:.2f}%")

# 2. Porcentaje No Show
pct_no_show = (df_master['NoShow'].sum() / len(df_master)) * 100
col2.metric("Tasa de No Show", f"{pct_no_show:.2f}%")

# 6. Porcentaje Late Check-In
late_mask = df_master['LateCheckIn'].astype(str).str.strip().str.lower().isin(['1', 'true', 'sí', 'si', 'yes', '-1'])
pct_late = late_mask.mean() * 100
col3.metric("Late Check-In", f"{pct_late:.2f}%")

# 5. Hora promedio de llegada
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
    else:
        st.info("Datos geográficos no disponibles.")

st.markdown("---")


# ================= SECCIÓN 3: ANÁLISIS FINANCIERO Y HABITACIONES =================
st.header("3. Ingresos y Categorías de Habitación")
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
    st.subheader("Resumen de Tickets y Consumos")
    
    # 11. Ticket Promedio
    ticket_promedio = df_master.groupby('tipo_habitacion')['monto_reserva_origen'].mean()
    cat_ticket_alto = ticket_promedio.idxmax()
    st.write(f"**Categoría con ticket promedio más alto:** {cat_ticket_alto} (${ticket_promedio.max():,.2f})")
    
    # 8. Categoría más utilizada
    uso_cat = df_master['tipo_habitacion'].value_counts()
    st.write(f"**Categoría más reservada:** {uso_cat.idxmax()} ({uso_cat.max()} reservas)")
    
    # 10. Método de pago
    if 'MetodoPago' in df_consumo.columns:
        metodo_top = df_consumo['MetodoPago'].value_counts()
        st.write(f"**Método de pago preferido:** {metodo_top.idxmax()} ({metodo_top.max()} usos)")
        
    # 13. Servicios adicionales
    consumo_por_habitacion = pd.merge(df_consumo, df_master[['ReservaID', 'tipo_habitacion']], on='ReservaID', how='inner')
    servicios_adicionales_hab = consumo_por_habitacion.groupby('tipo_habitacion')['Monto'].sum()
    if not servicios_adicionales_hab.empty:
        hab_mas_servicios = servicios_adicionales_hab.idxmax()
        st.write(f"**Habitación con más gastos extras:** {hab_mas_servicios} (${servicios_adicionales_hab.max():,.2f})")

st.markdown("---")


# ================= SECCIÓN 4: COMPORTAMIENTO DEL HUÉSPED =================
st.header("4. Comportamiento del Huésped")
col1, col2 = st.columns(2)

with col1:
    st.subheader("Relación: Noches vs Gasto Total")
    # Preparar datos
    gastos_adicionales = df_consumo.groupby('ReservaID')['Monto'].sum().reset_index()
    gastos_adicionales.rename(columns={'Monto': 'GastoConsumos'}, inplace=True)
    df_relacion = pd.merge(df_master[['ReservaID', 'noches', 'monto_reserva_origen']], gastos_adicionales, on='ReservaID', how='left')
    df_relacion['GastoConsumos'] = df_relacion['GastoConsumos'].fillna(0)
    df_relacion['GastoTotal'] = df_relacion['monto_reserva_origen'] + df_relacion['GastoConsumos']
    
    correlacion = df_relacion['noches'].corr(df_relacion['GastoTotal'])
    
    fig4, ax4 = plt.subplots(figsize=(8, 5))
    sns.scatterplot(data=df_relacion, x='noches', y='GastoTotal', alpha=0.6, color='purple', ax=ax4)
    sns.regplot(data=df_relacion, x='noches', y='GastoTotal', scatter=False, color='black', ax=ax4) # Línea de tendencia
    ax4.set_xlabel('Cantidad de Noches')
    ax4.set_ylabel('Gasto Total ($)')
    st.pyplot(fig4)
    st.caption(f"Coeficiente de correlación de Pearson: **{correlacion:.3f}**")

with col2:
    st.subheader("Top Nacionalidades por Consumo Extra")
    df_consumo_master = pd.merge(df_consumo, df_master[['ReservaID', 'EnglishCountryRegionName']], on='ReservaID', how='inner')
    consumo_nacionalidad = df_consumo_master.groupby('EnglishCountryRegionName')['Monto'].sum().reset_index()
    
    if not consumo_nacionalidad.empty:
        consumo_nacionalidad = consumo_nacionalidad.sort_values('Monto', ascending=False).head(5)
        fig5, ax5 = plt.subplots(figsize=(8, 5))
        sns.barplot(data=consumo_nacionalidad, y='EnglishCountryRegionName', x='Monto', palette='Oranges_r', ax=ax5)
        ax5.set_xlabel('Consumo Total ($)')
        ax5.set_ylabel('País')
        st.pyplot(fig5)
    else:
        st.info("No hay suficientes datos de consumo para calcularlo.")