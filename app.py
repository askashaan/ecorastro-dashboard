import streamlit as st
import folium
from streamlit_folium import st_folium
import ee
import json

# ---------------------------------------------------------
# 1. Configuración de Página
# ---------------------------------------------------------
st.set_page_config(
    page_title="EcoRastro | Planificación de Corredores Verdes",
    page_icon="🛰️",
    layout="wide"
)

st.title("🛰️ EcoRastro: Inteligencia Geoespacial & Corredores Verdes")
st.markdown("""
Plataforma B2G de apoyo a la toma de decisiones para la **Municipalidad de Santiago y el GORE**. 
Monitoreo satelital en vivo (*Sentinel-2 vía Google Earth Engine*) para la identificación de islas de calor y planificación de infraestructura verde urbana.
""")

# ---------------------------------------------------------
# 2. Inicialización de Google Earth Engine (Real)
# ---------------------------------------------------------
@st.cache_resource
def init_earth_engine():
    try:
        # Autenticación mediante credenciales del proyecto de Google Cloud
        # Reemplaza 'tu-proyecto-gee-id' por tu ID de proyecto de Google Earth Engine
        ee.Initialize(project='tu-proyecto-gee-id')
        return True
    except Exception as e:
        return str(e)

ee_status = init_earth_engine()

# ---------------------------------------------------------
# 3. Definición Geográfica Real del Parque O'Higgins
# ---------------------------------------------------------
# Polígono preciso del Parque O'Higgins (Latitud/Longitud real)
coordenadas_parque = [
    [-70.6625, -33.4578],
    [-70.6552, -33.4578],
    [-70.6552, -33.4672],
    [-70.6625, -33.4672],
    [-70.6625, -33.4578]
]

parque_geometry = ee.Geometry.Polygon(coordenadas_parque)

# ---------------------------------------------------------
# 4. Procesamiento de Imágenes Satelitales en Tiempo Real
# ---------------------------------------------------------
def obtener_capa_satelital_real(capa_tipo):
    if ee_status is not True:
        return None, None

    # Consulta a la colección multiespectral de Sentinel-2 (Harmonized)
    coleccion = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(parque_geometry)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 15))
        .sort("system:time_start", False)  # Tomar la más reciente disponible
    )

    imagen = coleccion.first()

    if capa_tipo == "NDVI (Salud Vegetal)":
        # Cálculo: (B8 - B4) / (B8 + B4)
        ndvi = imagen.normalizedDifference(["B8", "B4"]).rename("NDVI")
        corte = ndvi.clip(parque_geometry)
        
        vis_params = {
            "min": 0.0,
            "max": 0.8,
            "palette": ["#d73027", "#f46d43", "#fdae61", "#fee08b", "#d9ef8b", "#a6d96a", "#1a9850"]
        }
        
        map_id = corte.getMapId(vis_params)
        
        # Calcular estadística promedio real
        mean_stat = corte.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=parque_geometry,
            scale=10
        ).getInfo()
        
        return map_id["tile_fetcher"].url_format, mean_stat.get("NDVI", 0)

    else:
        # NDWI (Estrés Hídrico): (B3 - B8) / (B3 + B8)
        ndwi = imagen.normalizedDifference(["B3", "B8"]).rename("NDWI")
        corte = ndwi.clip(parque_geometry)
        
        vis_params = {
            "min": -0.5,
            "max": 0.2,
            "palette": ["#d73027", "#f46d43", "#fee08b", "#e0f3f8", "#91bfdb", "#4575b4"]
        }
        
        map_id = corte.getMapId(vis_params)
        
        mean_stat = corte.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=parque_geometry,
            scale=10
        ).getInfo()
        
        return map_id["tile_fetcher"].url_format, mean_stat.get("NDWI", 0)

# ---------------------------------------------------------
# 5. Interfaz de Usuario & Dashboard
# ---------------------------------------------------------
st.sidebar.header("⚙️ Filtros Satelitales")
capa_seleccionada = st.sidebar.radio(
    "Selecciona el indicador multiespectral:",
    ["NDVI (Salud Vegetal)", "NDWI (Estrés Hídrico)"]
)

# Renderizar Mapa Base
m = folium.Map(
    location=[-33.4625, -70.6588],
    zoom_start=15,
    tiles="CartoDB dark_matter"
)

if ee_status is True:
    tile_url, promedio_val = obtener_capa_satelital_real(capa_seleccionada)
    
    if tile_url:
        # Superponer la capa de teselas en vivo generada por Google Earth Engine
        folium.TileLayer(
            tiles=tile_url,
            attr="Google Earth Engine / Copernicus Sentinel-2",
            name=capa_seleccionada,
            overlay=True,
            control=True
        ).add_to(m)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Fuente de Datos", "Sentinel-2 (ESA)")
        with col2:
            st.metric("Resolución Espacial", "10 metros / píxel")
        with col3:
            st.metric(f"Promedio Real {capa_seleccionada.split()[0]}", f"{promedio_val:.3f}")
    else:
        st.warning("No se pudieron cargar las imágenes de la última pasada orbital.")
else:
    st.info("💡 **Modo Demostración Activo:** Para habilitar las consultas automatizadas a Earth Engine en producción, configure la variable de credenciales del proyecto de Google Cloud.")

# Mostrar Mapa
st_folium(m, width="100%", height=550)

st.markdown("---")
st.caption("EcoRastro B2G | Integración oficial con API de Google Earth Engine para la estrategia de Corredores Verdes en la Región Metropolitana.")
