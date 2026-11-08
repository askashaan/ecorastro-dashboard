import streamlit as st
import folium
from streamlit_folium import st_folium
import numpy as np
import random

# 1. Configuración de la página
st.set_page_config(page_title="EcoRastro Dashboard", layout="wide")

st.title("🛰️ EcoRastro: Inteligencia Geoespacial Urbana")
st.markdown("""
**La información biológica está fragmentada y desactualizada.**
Actualmente no existe un monitoreo integral en el Parque O'Higgins. Este panel centralizado utiliza datos satelitales simulados (Sentinel-2) para entregar métricas de salud vegetal y estrés hídrico en tiempo real, optimizando recursos y previniendo riesgos sin requerir personal en terreno.
""")

# 2. Barra lateral para los controles
st.sidebar.header("Panel de Control")
capa_activa = st.sidebar.radio(
    "Selecciona la capa de análisis satelital:",
    ("Índice de Salud (NDVI)", "Estrés Hídrico (NDWI)")
)

# Tarjeta de alerta dinámica
if capa_activa == "Índice de Salud (NDVI)":
    st.sidebar.success("📊 Salud Vegetal Promedio: 78% - Estado Óptimo general, con zonas aisladas de baja biomasa.")
else:
    st.sidebar.error("⚠️ Alerta Crítica: Estrés hídrico detectado en Sector Norte (Fantasilandia). Priorizar ruta de riego.")

# 3. Creación del Mapa base centrado en el Parque O'Higgins
m = folium.Map(location=[-33.4620, -70.6600], zoom_start=15, tiles="CartoDB positron")

# 4. Generación del "Raster" (Malla de píxeles simulados)
# Límites del parque
lat_start, lat_end = -33.4580, -33.4670
lng_start, lng_end = -70.6620, -70.6555
paso = 0.0004 # Tamaño del píxel (~40 metros)

for lat in np.arange(lat_end, lat_start, paso):
    for lng in np.arange(lng_start, lng_end, paso):
        
        # Excluir la elipse central pavimentada
        if -33.4645 < lat < -33.4605 and -70.6610 < lng < -70.6580:
            continue
            
        # Lógica de colores según el índice seleccionado
        if capa_activa == "Índice de Salud (NDVI)":
            # Tonos verdes simulando salud vegetal
            color = "#238b45" if random.random() > 0.4 else "#74c476"
        else:
            # Estrés hídrico: Rojo al norte (latitudes mayores), azul al sur
            if lat > -33.4610:
                color = "#cb181d" if random.random() > 0.3 else "#fb6a4a" # Zonas rojas/naranjas
            else:
                color = "#2171b5" if random.random() > 0.2 else "#6baed6" # Zonas regadas (azul)

        # Dibujar el "píxel" en el mapa
        folium.Rectangle(
            bounds=[[lat, lng], [lat + paso, lng + paso]],
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.65,
            weight=0 # Sin bordes para que parezca una mancha continua
        ).add_to(m)

# 5. Renderizar el mapa en Streamlit
st_folium(m, width=1000, height=600)
