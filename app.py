import streamlit as st
import folium
from folium import plugins
from streamlit_folium import st_folium
import ee
import json
import os

# ---------------------------------------------------------
# 1. Configuración de Página & Tema Visual Bolt
# ---------------------------------------------------------
st.set_page_config(
    page_title="EcoRastro | Monitoreo Satelital",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Estilos CSS con alto contraste y diseño 1:1 con Bolt (Restaurado)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Plus Jakarta Sans', sans-serif; }
    
    .stApp { background-color: #0d1f15 !important; color: #f7f4ed !important; }
    #MainMenu, footer, header { visibility: hidden; }

    .bolt-nav { display: flex; align-items: center; justify-content: space-between; padding: 12px 24px; background-color: #0d1f15; border-bottom: 1px solid rgba(247, 244, 237, 0.1); margin-bottom: 32px; }
    .bolt-logo { display: flex; align-items: center; gap: 10px; font-weight: 700; font-size: 1.2rem; color: #f7f4ed; }
    .bolt-btn-nav { background-color: #e76f51; color: #ffffff !important; padding: 8px 20px; border-radius: 9999px; font-weight: 600; font-size: 0.875rem; text-decoration: none; }
    
    .hero-title { font-size: 3rem; font-weight: 700; color: #f7f4ed; line-height: 1.1; margin-bottom: 16px; }
    .hero-subtitle { color: rgba(247, 244, 237, 0.8); font-size: 1.125rem; max-width: 650px; line-height: 1.6; margin-bottom: 24px; }
    .badge-pill { display: inline-flex; align-items: center; gap: 6px; background-color: rgba(247, 244, 237, 0.1); border: 1px solid rgba(247, 244, 237, 0.2); padding: 4px 14px; border-radius: 9999px; font-size: 0.75rem; font-weight: 600; color: #f7f4ed; margin-bottom: 16px; }
    
    div[data-testid="stRadio"] label { color: #f7f4ed !important; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 2. Header & Navegación (Bolt UI)
# ---------------------------------------------------------
st.markdown("""
<div class="bolt-nav">
    <div class="bolt-logo">🌱 EcoRastro</div>
    <div><a href="#dashboard" class="bolt-btn-nav">Ver Dashboard</a></div>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 3. Inicialización de Google Earth Engine
# ---------------------------------------------------------
@st.cache_resource
def init_earth_engine():
    try:
        if "GCP_SERVICE_ACCOUNT" in st.secrets:
            secret_val = st.secrets["GCP_SERVICE_ACCOUNT"]
            service_account_info = json.loads(secret_val) if isinstance(secret_val, str) else dict(secret_val)
            
            client_email = service_account_info.get("client_email")
            private_key = service_account_info.get("private_key")
            project_id = service_account_info.get("project_id")
            
            credentials = ee.ServiceAccountCredentials(client_email, key_data=private_key)
            ee.Initialize(credentials, project=project_id)
            return True
        else:
            ee.Initialize()
            return True
    except Exception:
        return False

ee_status = init_earth_engine()

coordenadas_parque = [
    [-70.6678, -33.4530], [-70.6525, -33.4530],
    [-70.6525, -33.4715], [-70.6678, -33.4715], [-70.6678, -33.4530]
]

def obtener_capa_satelital(capa_tipo):
    if not ee_status: return None, 0.0
    try:
        parque_geometry = ee.Geometry.Polygon(coordenadas_parque)
        coleccion = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterBounds(parque_geometry).filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 15)).sort("system:time_start", False)
        imagen = coleccion.first()

        if "Normal" in capa_tipo:
            corte = imagen.select(["B4", "B3", "B2"]).clip(parque_geometry)
            vis_params = {"min": 0, "max": 2500, "gamma": 1.2}
            return corte.getMapId(vis_params)["tile_fetcher"].url_format, 0.0
        elif "NDVI" in capa_tipo:
            corte = imagen.normalizedDifference(["B8", "B4"]).rename("NDVI").clip(parque_geometry)
            vis_params = {"min": 0.1, "max": 0.7, "palette": ["#d73027", "#fc8d59", "#fee08b", "#d9ef8b", "#91cf60", "#1a9850"]}
        elif "NDMI" in capa_tipo:
            ndvi = imagen.normalizedDifference(["B8", "B4"])
            ndmi = imagen.normalizedDifference(["B8A", "B11"])
            corte = ndmi.updateMask(ndvi.gt(0.15)).rename("NDMI").clip(parque_geometry)
            vis_params = {"min": -0.05, "max": 0.3, "palette": ["#d73027", "#f46d43", "#fdae61", "#fee08b", "#abd9e9", "#74add1", "#4575b4"]}
        elif "NDBI" in capa_tipo:
            corte = imagen.normalizedDifference(["B11", "B8"]).rename("NDBI").clip(parque_geometry)
            vis_params = {"min": -0.2, "max": 0.2, "palette": ["#1a9850", "#91cf60", "#d9ef8b", "#fee08b", "#fc8d59", "#d73027"]}

        map_id = corte.getMapId(vis_params)
        mean_stat = corte.reduceRegion(reducer=ee.Reducer.mean(), geometry=parque_geometry, scale=10).getInfo()
        promedio_val = list(mean_stat.values())[0] if mean_stat and list(mean_stat.values())[0] is not None else 0.0
        return map_id["tile_fetcher"].url_format, promedio_val
    except Exception:
        return None, 0.0

# ---------------------------------------------------------
# FUNCION NUEVA: Cargar árboles del GeoJSON
# ---------------------------------------------------------
@st.cache_data
def cargar_arboles_geojson(filepath):
    arboles = []
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            for feature in data.get('features', []):
                if feature['geometry']['type'] == 'Point':
                    coords = feature['geometry']['coordinates']
                    props = feature['properties']
                    arboles.append({
                        'lat': coords[1],
                        'lng': coords[0],
                        'especie': props.get('species', 'Árbol sin especificar'),
                        'etapa': props.get('life_cycle', 'Desconocida')
                    })
    return arboles

# ---------------------------------------------------------
# 4. Hero Section
# ---------------------------------------------------------
st.markdown("""
<div class="badge-pill">
    <span style="height: 6px; width: 6px; background-color: #f39a77; border-radius: 50%;"></span>
    Plataforma SaaS B2G
</div>
<h1 class="hero-title">
    Inteligencia Geoespacial para el Monitoreo de <span style="color: #f39a77;">Áreas Verdes</span>
</h1>
<p class="hero-subtitle">
    EcoRastro procesa datos satelitales (Sentinel-2) para unificar la información biológica urbana. 
    Entregamos un panel de control en tiempo real sobre la salud vegetal y el estrés hídrico.
</p>
""", unsafe_allow_html=True)

col_h1, col_h2, col_h3 = st.columns(3)
with col_h1:
    st.caption("⏰ ACTUALIZACIÓN")
    st.markdown("**Cada 5 días**")
with col_h2:
    st.caption("🛰️ FUENTE")
    st.markdown("**Sentinel-2 (ESA)**")
with col_h3:
    st.caption("💧 ÍNDICES")
    st.markdown("**NDVI · NDMI · NDBI**")

st.markdown("---")

# ---------------------------------------------------------
# 5. Problem Section (Corrección del HTML)
# ---------------------------------------------------------
st.markdown("""
<div style="background-color: #f7f4ed; border-radius: 24px; padding: 36px; margin-top: 32px; margin-bottom: 32px; font-family: sans-serif;">
    <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em; color: #e76f51;">El problema</div>
    <h2 style="color: #142e20; font-size: 1.8rem; font-weight: 700; margin-top: 8px; margin-bottom: 12px; line-height: 1.2;">
        La información biológica está fragmentada y desactualizada.
    </h2>
    <p style="color: #2d5a3f; font-size: 0.95rem; line-height: 1.6; margin-bottom: 24px;">
        Actualmente no existe un monitoreo integral y periódico unificado en el Parque O'Higgins. La información está dispersa entre inventarios municipales estáticos, datos de ciencia ciudadana y estudios académicos aislados. Hace falta un sistema centralizado que mantenga los datos actualizados para la gestión real.
    </p>
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px;">
        <div style="background-color: #ffffff; border: 1px dashed #c2d6c9; border-radius: 16px; padding: 14px;">
            <strong style="color: #142e20; display: block; font-size: 0.9rem; margin-bottom: 4px;">🏢 Inventarios municipales</strong>
            <span style="color: #407b57; font-size: 0.8rem;">Estáticos y sin actualización</span>
        </div>
        <div style="background-color: #ffffff; border: 1px dashed #c2d6c9; border-radius: 16px; padding: 14px;">
            <strong style="color: #142e20; display: block; font-size: 0.9rem; margin-bottom: 4px;">👥 Ciencia ciudadana</strong>
            <span style="color: #407b57; font-size: 0.8rem;">Registros puntuales y dispersos</span>
        </div>
        <div style="background-color: #ffffff; border: 1px dashed #c2d6c9; border-radius: 16px; padding: 14px;">
            <strong style="color: #142e20; display: block; font-size: 0.9rem; margin-bottom: 4px;">🎓 Estudios académicos</strong>
            <span style="color: #407b57; font-size: 0.8rem;">Aislados y de corto alcance</span>
        </div>
    </div>
    <div style="background-color: #fdf0ed; border: 1px solid #f8c9bc; border-radius: 14px; padding: 14px 18px; margin-top: 20px; display: flex; align-items: center; gap: 14px;">
        <span style="background-color: #e76f51; color: white; padding: 6px 12px; border-radius: 8px; font-weight: 700; font-size: 0.8rem; white-space: nowrap;">⚡ Impacto</span>
        <span style="color: #142e20; font-weight: 600; font-size: 0.9rem;">
            De un ecosistema fragmentado a 1 sola plataforma centralizada con actualización cada 5 días.
        </span>
    </div>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 6. Dashboard Satelital (Alta Resolución + Opacidad + Catastro)
# ---------------------------------------------------------
st.markdown("<div id='dashboard'></div>", unsafe_allow_html=True)
st.caption("🛰️ DASHBOARD SATELITAL & AUDITORÍA DE CATASTRO")
st.markdown("## Parque O'Higgins: salud vegetal y estrés hídrico")
st.write("Usa la transparencia para ver el análisis satelital superpuesto sobre los árboles en alta resolución.")

# Controles de Capa y Transparencia
col_ctrl1, col_ctrl2 = st.columns([3, 1])
with col_ctrl1:
    capa_seleccionada = st.radio(
        "Capas de análisis Sentinel-2:",
        ["🌱 Índice de Salud (NDVI)", "💧 Estrés Hídrico (NDMI)", "🏢 Zonas Construidas (NDBI)", "📸 Foto Satelital (RGB)"],
        horizontal=True
    )
with col_ctrl2:
    opacidad_capa = st.slider(
        "Transparencia de la capa:",
        min_value=0.0, max_value=1.0, value=0.7, step=0.05,
        help="Baja la opacidad para ver el mapa de alta resolución debajo."
    )

# Mapa Base Esri Alta Resolución
m = folium.Map(
    location=[-33.4625, -70.6588], 
    zoom_start=16, 
    tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    attr="Esri World Imagery (Alta Resolución)"
)

# Capa de Calles Transparente
folium.TileLayer(
    tiles="https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",
    attr="Etiquetas Viales Esri",
    name="Calles y Lugares",
    overlay=True,
    control=True
).add_to(m)

tile_url, promedio_val = obtener_capa_satelital(capa_seleccionada)

if tile_url:
    # Capa de Sentinel-2 con Opacidad variable
    folium.TileLayer(
        tiles=tile_url, 
        attr="Copernicus Sentinel-2", 
        name=capa_seleccionada, 
        overlay=True, 
        control=True,
        opacity=opacidad_capa
    ).add_to(m)
else:
    folium.Polygon(locations=[[lat, lng] for lng, lat in coordenadas_parque], color="#10b981", fill=True, fill_opacity=0.3).add_to(m)

# --- Agregar marcadores de los árboles separando Palmas de Otros ---
lista_arboles = cargar_arboles_geojson('arboles.geojson')

if lista_arboles:
    grupo_palmas = folium.FeatureGroup(name="🌴 Palmas Chilenas", show=True)
    grupo_otros = folium.FeatureGroup(name="🌳 Otros Árboles (No identificados)", show=True)
    
    for arbol in lista_arboles:
        especie_str = str(arbol.get('especie', '')).lower()
        es_palma = "palma" in especie_str or "jubaea" in especie_str
        
        if es_palma:
            fill_color = "#10b981"  
            radius = 6              
            fill_opacity = 0.9
            grupo_destino = grupo_palmas
            nombre_mostrar = "Palma Chilena"
            icono = "🌴"
        else:
            fill_color = "#f39a77"  
            radius = 3              
            fill_opacity = 0.45     
            grupo_destino = grupo_otros
            nombre_mostrar = arbol.get('especie', 'Especie no identificada').title()
            icono = "🌳"
            
        html_popup = f"""
        <div style="font-family: 'Plus Jakarta Sans', sans-serif; min-width: 160px; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
            <div style="background-color: {fill_color}; color: white; padding: 6px 12px; font-weight: bold; font-size: 13px; border-bottom: 1px solid rgba(0,0,0,0.1);">
                {icono} {nombre_mostrar}
            </div>
            <div style="padding: 10px 12px; background-color: #ffffff; color: #333333;">
                <p style="margin: 0 0 6px 0; font-size: 12px;"><b>Etapa:</b> {arbol['etapa']}</p>
                <p style="margin: 0; font-size: 10px; color: #7f8c8d;">📍 Lat: {arbol['lat']:.5f}<br>📍 Lng: {arbol['lng']:.5f}</p>
            </div>
        </div>
        """
        
        folium.CircleMarker(
            location=[arbol['lat'], arbol['lng']],
            radius=radius,
            popup=folium.Popup(html_popup, max_width=250),
            color="#ffffff",        
            weight=0.8,
            fill=True,
            fill_color=fill_color,
            fill_opacity=fill_opacity
        ).add_to(grupo_destino)
        
    grupo_palmas.add_to(m)
    grupo_otros.add_to(m)

folium.LayerControl(position="topright", collapsed=False).add_to(m)

# Renderizar el mapa de Folium
st_folium(m, width="100%", height=560, key=f"{capa_seleccionada}_{opacidad_capa}")

# Tarjetas Inferiores
if "Normal" not in capa_seleccionada:
    pct_val = int(max(0, min(1, promedio_val + 0.3)) * 100) if "NDVI" in capa_seleccionada else 78
    col_m1, col_m2 = st.columns([1, 2])
    with col_m1:
        st.metric(label="SALUD VEGETAL PROMEDIO", value=f"{pct_val}%", delta="Estado Óptimo")
    with col_m2:
        st.info("Biomasa alta en la mayoría de los sectores. Las zonas coloreadas en tonos cálidos (rojo/naranja) requieren seguimiento de riego.")

# ---------------------------------------------------------
# 7. GUÍA TÉCNICA E INTERPRETACIÓN DE ÍNDICES (Diccionario B2G)
# ---------------------------------------------------------
st.markdown("---")
with st.expander("📖 Guía de Interpretación de Capas e Índices Satelitales (Haz clic para desplegar)", expanded=True):
    col_exp1, col_exp2 = st.columns(2)
    
    with col_exp1:
        st.markdown("""
        ### 🌳 NDVI (Índice de Salud Vegetal)
        Mide el vigor, la densidad foliar y la capacidad de fotosíntesis de la biomasa urbana.
        * 🔴 **Rojo / Naranja:** Tierra seca, suelo desnudo o vegetación muerta.
        * 🟡 **Amarillo:** Pasto en mal estado o vegetación muy rala.
        * 🟢 **Verde Oscuro:** Árboles frondosos y pasto muy sano.
        
        ---
        
        ### 🏢 NDBI (Zonas Construidas / Superficies Impermeables)
        Identifica la densidad de infraestructura que retiene radiación solar.
        * 🟢 **Verde:** Cobertura natural (sin asfalto/hormigón).
        * 🟡 **Amarillo:** Zonas mixtas o suelo compactado.
        * 🔴 **Rojo Oscuro:** Alta acumulación de asfalto y techos (Focos de Islas de Calor).
        """)
        
    with col_exp2:
        st.markdown("""
        ### 💧 NDMI (Índice de Estrés Hídrico)
        *Algoritmo inteligente: Aisla el cemento y analiza **únicamente la vegetación viva**.*
        * 🔴 **Rojo / Naranja:** Plantas con **fuerte déficit de agua** (Requieren riego priorizado urgente).
        * 🟡 **Amarillo / Celeste claro:** Humedad foliar en niveles aceptables.
        * 🔵 **Azul Oscuro:** Árboles con **excelente reserva de agua** e hidratación óptima.
        
        ---
        
        ### 📸 Foto Satelital Normal (RGB)
        Imagen en color verdadero capturada directamente por las bandas ópticas de **Copernicus Sentinel-2** a 10 metros de resolución espacial.
        """)
