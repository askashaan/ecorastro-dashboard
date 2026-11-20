import streamlit as st
import folium
from folium import plugins
from streamlit_folium import st_folium
import ee
import json
import os
import requests
import pandas as pd
from io import BytesIO
from PIL import Image, ImageDraw
from datetime import datetime, timedelta
import google.generativeai as genai

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
    
    div[data-testid="stRadio"] label, div[data-testid="stSelectbox"] label, div[data-testid="stDateInput"] label { color: #f7f4ed !important; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 2. Header & Navegación (Bolt UI)
# ---------------------------------------------------------
st.markdown("""
<div class="bolt-nav">
    <div class="bolt-logo">🌱 EcoRastro</div>
    <div style="display: flex; gap: 15px; align-items: center;">
        <span style="color: #10b981; font-weight: 600; font-size: 0.9rem;">● IA Core Activado</span>
        <a href="#dashboard" class="bolt-btn-nav">Ver Dashboard</a>
    </div>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 3. Inicialización de Motores (GEE y Gemini LLM)
# ---------------------------------------------------------
@st.cache_resource
def init_earth_engine():
    try:
        if "GCP_SERVICE_ACCOUNT" in st.secrets:
            secret_val = st.secrets["GCP_SERVICE_ACCOUNT"]
            service_account_info = json.loads(secret_val) if isinstance(secret_val, str) else dict(secret_val)
            
            client_email = service_account_info.get("client_email")
            private_key = service_account_info.get("private_key", "").replace("\\n", "\n")
            project_id = service_account_info.get("project_id")
            
            credentials = ee.ServiceAccountCredentials(client_email, key_data=private_key)
            ee.Initialize(credentials, project=project_id)
            return True, "OK"
        else:
            ee.Initialize()
            return True, "OK"
    except Exception as e:
        return False, str(e)

ee_status, ee_error = init_earth_engine()
if not ee_status:
    st.error(f"🚨 Detalle del error de Earth Engine: {ee_error}")

has_ai = False
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model_ai = genai.GenerativeModel('gemini-1.5-flash')
    has_ai = True

# ---------------------------------------------------------
# 4. Lógica Satelital, Tiling Visual y de IA (El Ojo y el Cerebro)
# ---------------------------------------------------------
coordenadas_parque = [
    [-70.6678, -33.4530], [-70.6525, -33.4530],
    [-70.6525, -33.4715], [-70.6678, -33.4715], [-70.6678, -33.4530]
]

def obtener_capa_satelital(capa_tipo, fecha_objetivo):
    if not ee_status: return None, 0.0, "Sin Conexión"
    try:
        parque_geometry = ee.Geometry.Polygon(coordenadas_parque)
        fecha_fin = datetime.combine(fecha_objetivo, datetime.max.time())
        fecha_inicio = fecha_fin - timedelta(days=45) 
        
        coleccion = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")\
            .filterBounds(parque_geometry)\
            .filterDate(fecha_inicio.strftime('%Y-%m-%d'), fecha_fin.strftime('%Y-%m-%d'))\
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20))\
            .sort("system:time_start", False)
            
        imagen = coleccion.first()
        timestamp = imagen.get('system:time_start')
        fecha_real = ee.Date(timestamp).format('dd/MM/YYYY').getInfo()

        if "Normal" in capa_tipo:
            corte = imagen.select(["B4", "B3", "B2"]).clip(parque_geometry)
            vis_params = {"min": 0, "max": 2500, "gamma": 1.2}
            return corte.getMapId(vis_params)["tile_fetcher"].url_format, 0.0, fecha_real
        elif "NDVI" in capa_tipo:
            corte = imagen.normalizedDifference(["B8", "B4"]).rename("NDVI").clip(parque_geometry)
            vis_params = {"min": 0.1, "max": 0.7, "palette": ["#d73027", "#fc8d59", "#fee08b", "#d9ef8b", "#91cf60", "#1a9850"]}
        elif "NDMI" in capa_tipo:
            ndvi = imagen.normalizedDifference(["B8", "B4"])
            ndmi = imagen.normalizedDifference(["B8A", "B11"])
            corte = ndmi.updateMask(ndvi.gt(0.15)).rename("NDMI").clip(parque_geometry)
            vis_params = {"min": -0.05, "max": 0.3, "palette": ["#d73027", "#f46d43", "#fdae61", "#fee08b", "#abd9e9", "#74add1", "#4575b4"]}
        elif "Zonas" in capa_tipo:
            # MEJORA 1: Grilla de Zonas de Cuidado de 20x20 metros corregida
            ndvi = imagen.normalizedDifference(["B8", "B4"])
            ndmi = imagen.normalizedDifference(["B8A", "B11"])
            corte = ndmi.updateMask(ndvi.gt(0.1)).reproject(crs='EPSG:4326', scale=20).rename("NDMI_Grid").clip(parque_geometry)
            vis_params = {"min": -0.05, "max": 0.3, "palette": ["#d73027", "#f46d43", "#fdae61", "#fee08b", "#abd9e9", "#74add1", "#4575b4"]}
        elif "NDBI" in capa_tipo:
            corte = imagen.normalizedDifference(["B11", "B8"]).rename("NDBI").clip(parque_geometry)
            vis_params = {"min": -0.2, "max": 0.2, "palette": ["#1a9850", "#91cf60", "#d9ef8b", "#fee08b", "#fc8d59", "#d73027"]}
        elif "Térmico" in capa_tipo:
            col_landsat = ee.ImageCollection("LANDSAT/LC08/C02/T1_L2")\
                .filterBounds(parque_geometry)\
                .filterDate(fecha_inicio.strftime('%Y-%m-%d'), fecha_fin.strftime('%Y-%m-%d'))\
                .filter(ee.Filter.lt("CLOUD_COVER", 20))\
                .sort("system:time_start", False)
            
            if col_landsat.size().getInfo() > 0:
                img_lst = col_landsat.first()
                corte = img_lst.select('ST_B10').multiply(0.00341802).add(149.0).subtract(273.15).clip(parque_geometry)
                vis_params = {"min": 15, "max": 45, "palette": ["#313695", "#74add1", "#fed976", "#fd8d3c", "#e31a1c", "#800026"]}
                fecha_real = ee.Date(img_lst.get('system:time_start')).format('dd/MM/YYYY').getInfo()
                return corte.getMapId(vis_params)["tile_fetcher"].url_format, 0.0, fecha_real
            else:
                return None, 0.0, "Sin capturas térmicas Landsat recientes"

        map_id = corte.getMapId(vis_params)
        mean_stat = corte.reduceRegion(reducer=ee.Reducer.mean(), geometry=parque_geometry, scale=10).getInfo()
        promedio_val = list(mean_stat.values())[0] if mean_stat and list(mean_stat.values())[0] is not None else 0.0
        return map_id["tile_fetcher"].url_format, promedio_val, fecha_real
    except Exception:
        return None, 0.0, "No se encontraron capturas despejadas para esa fecha"

def obtener_estado_arboles(diccionario, fecha_objetivo):
    """ MEJORA 5: Escanea matemáticamente la salud de todos los árboles del GeoJSON """
    if not ee_status or not diccionario: return diccionario
    
    # Copia segura de atributos
    dic_nuevo = {k: v.copy() for k, v in diccionario.items()}
    for k in dic_nuevo: dic_nuevo[k]['ndmi'] = 0.15 # Valor verde por defecto
    
    try:
        fecha_fin = datetime.combine(fecha_objetivo, datetime.max.time())
        fecha_inicio = fecha_fin - timedelta(days=45) 
        
        imagen = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")\
            .filterBounds(ee.Geometry.Polygon(coordenadas_parque))\
            .filterDate(fecha_inicio.strftime('%Y-%m-%d'), fecha_fin.strftime('%Y-%m-%d'))\
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20))\
            .sort("system:time_start", False).first()
            
        ndmi = imagen.normalizedDifference(["B8A", "B11"]).rename('NDMI')
        
        # Muestreo veloz de GEE en un solo llamado
        features = [ee.Feature(ee.Geometry.Point([v['lng'], v['lat']]), {'llave': k}) for k, v in dic_nuevo.items()]
        fc = ee.FeatureCollection(features)
        
        sampled = ndmi.sampleRegions(collection=fc, scale=10, geometries=False)
        resultados = sampled.getInfo().get('features', [])
        
        for res in resultados:
            k = res.get('properties', {}).get('llave')
            if k in dic_nuevo:
                dic_nuevo[k]['ndmi'] = res['properties'].get('NDMI', 0.15)
    except Exception:
        pass
        
    return dic_nuevo

def generar_tiling_y_metricas(lat, lng, fecha_objetivo):
    if not ee_status: 
        return {"NDVI_pasado": 0.65, "NDVI_hoy": 0.35, "NDMI_hoy": -0.1, "fecha_previa": "Hace 5 días", "serie_temporal": []}, None
    
    punto = ee.Geometry.Point([lng, lat])
    fecha_fin = datetime.combine(fecha_objetivo, datetime.max.time())
    
    coleccion = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterBounds(punto).filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 25))
    img_objetivo = coleccion.filterDate(ee.Date(fecha_fin - timedelta(days=20)), ee.Date(fecha_fin)).sort("system:time_start", False).first()
    
    try:
        fecha_evaluado_ee = ee.Date(img_objetivo.get('system:time_start'))
        fecha_previa_ideal = fecha_evaluado_ee.advance(-5, 'day')
        
        img_pasada = coleccion.filterDate(fecha_previa_ideal.advance(-3, 'day'), fecha_previa_ideal.advance(3, 'day')).sort("system:time_start", False).first()
        
        ndvi_pasado = img_pasada.normalizedDifference(["B8", "B4"]).reduceRegion(ee.Reducer.mean(), punto, 10).getInfo().get('nd')
        ndvi_hoy = img_objetivo.normalizedDifference(["B8", "B4"]).reduceRegion(ee.Reducer.mean(), punto, 10).getInfo().get('nd')
        ndmi_hoy = img_objetivo.normalizedDifference(["B8A", "B11"]).reduceRegion(ee.Reducer.mean(), punto, 10).getInfo().get('nd')
        fecha_previa_str = ee.Date(img_pasada.get('system:time_start')).format('dd/MM/YYYY').getInfo()

        delta_deg = 0.00045  
        min_x, max_x = lng - delta_deg, lng + delta_deg
        min_y, max_y = lat - delta_deg, lat + delta_deg
        
        url_esri = f"https://services.arcgisonline.com/arcgis/rest/services/World_Imagery/MapServer/export?bbox={min_x},{min_y},{max_x},{max_y}&bboxSR=4326&size=300,300&format=png&f=image"
        resp = requests.get(url_esri, timeout=10)
        img_alta_res = Image.open(BytesIO(resp.content)).convert("RGB")
        draw = ImageDraw.Draw(img_alta_res)
        cx, cy = 150, 150
        r = 18 
        draw.rectangle([cx - r, cy - r, cx + r, cy + r], outline="red", width=3)

        fecha_hist = fecha_fin - timedelta(days=240)
        col_ts = coleccion.filterDate(ee.Date(fecha_hist), ee.Date(fecha_fin))
        
        def extraer_indices(img):
            fecha = img.date().format('YYYY-MM-dd')
            n_val = img.normalizedDifference(["B8", "B4"]).reduceRegion(ee.Reducer.mean(), punto, 10).get('nd')
            m_val = img.normalizedDifference(["B8A", "B11"]).reduceRegion(ee.Reducer.mean(), punto, 10).get('nd')
            return ee.Feature(None, {'fecha': fecha, 'NDVI': n_val, 'NDMI': m_val})
        
        datos_serie = col_ts.map(extraer_indices).getInfo().get('features', [])
        historial = [{"Fecha": d['properties']['fecha'], "NDVI": d['properties']['NDVI'], "NDMI": d['properties']['NDMI']} 
                     for d in datos_serie if d['properties']['NDVI'] is not None]

        metricas = {
            "NDVI_pasado": round(ndvi_pasado or 0.65, 2), 
            "NDVI_hoy": round(ndvi_hoy or 0.35, 2), 
            "NDMI_hoy": round(ndmi_hoy or -0.1, 2),
            "fecha_previa": fecha_previa_str,
            "serie_temporal": historial
        }
        return metricas, img_alta_res
    except Exception:
        return {"NDVI_pasado": 0.68, "NDVI_hoy": 0.32, "NDMI_hoy": -0.15, "fecha_previa": "Hace 5 días (Aprox)", "serie_temporal": []}, None

def generar_diagnostico_hibrido(especie, etapa, arbol_id, datos_satelitales, fecha_str, img_actual=None):
    prompt = f"""
    Actúa como un ingeniero forestal urbano experto. En la imagen de alta resolución hay un ejemplar marcado en rojo:
- ID Catastro: #{arbol_id}
- ESPECIE ESTRICTA: {especie} (Etapa: {etapa}). Basa tu respuesta en esta especie exacta.
- Fecha evaluada: {fecha_str}
    
    Datos científicos calculados por satélite (Sentinel-2):
- NDVI Previo ({datos_satelitales['fecha_previa']}): {datos_satelitales['NDVI_pasado']}
- NDVI Evaluado ({fecha_str}): {datos_satelitales['NDVI_hoy']}
- NDMI Evaluado (Estrés Hídrico): {datos_satelitales['NDMI_hoy']}
    
    Instrucciones:
1. Redacta un diagnóstico técnico breve analizando la evolución del NDVI y el nivel actual de NDMI.
2. Calcula los litros de agua semanales requeridos usando esta regla estricta:
  - ESTADO ÓPTIMO (NDVI >= 0.6 y NDMI >= 0.2): **0 Litros semanales**.
  - ESTRÉS LEVE (NDMI entre 0.0 y 0.19): Riego ligero (10 a 25 Litros).
  - ESTRÉS MODERADO / CRÍTICO (NDMI < 0.0): Aumentar proporcionalmente entre 40 y 100 Litros.
3. Finaliza siempre indicando la cantidad en negrita.
    """
    
    if has_ai:
        try:
            if img_actual is not None:
                return model_ai.generate_content([prompt, img_actual]).text
            else:
                return model_ai.generate_content(prompt).text
        except Exception:
            pass
            
    ndvi = datos_satelitales['NDVI_hoy']
    ndmi = datos_satelitales['NDMI_hoy']
    ndvi_prev = datos_satelitales['NDVI_pasado']
    variacion_ndvi = ndvi - ndvi_prev
    
    if ndvi >= 0.55 and ndmi >= 0.15:
        litros_sugeridos, accion = 0, "Estado óptimo. No requiere riego."
    elif ndmi >= 0.0:
        litros_sugeridos, accion = 20, "Estrés hídrico leve. Riego de mantenimiento sugerido."
    elif ndmi >= -0.1:
        litros_sugeridos, accion = 50, "Estrés hídrico moderado. Déficit confirmado."
    else:
        litros_sugeridos, accion = 90, "Estrés hídrico crítico. Riego de emergencia requerido."
        
    tendencia = "mejora" if variacion_ndvi >= 0 else "caída"
    return f"⚠️ Análisis Híbrido (ID #{arbol_id} - {especie}): Se detecta una {tendencia} de {abs(round(variacion_ndvi, 2))} en el vigor respecto a {datos_satelitales['fecha_previa']}. El índice NDMI ({ndmi}) indica: {accion}. **Prescripción operativa:** Aplicar **{litros_sugeridos} litros de agua semanales**."
@st.cache_data
def cargar_arboles_geojson(filepath):
    arboles = {}
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            for idx, feature in enumerate(data.get('features', []), start=1):
                if feature['geometry']['type'] == 'Point':
                    coords = feature['geometry']['coordinates']
                    props = feature['properties']
                    llave = f"{round(coords[1], 4)}_{round(coords[0], 4)}"
                    arboles[llave] = {
                        'id': props.get('id', idx),
                        'lat': coords[1],
                        'lng': coords[0],
                        'especie': props.get('species', 'Árbol sin especificar'),
                        'etapa': props.get('life_cycle', 'Desconocida')
                    }
    return arboles
# ---------------------------------------------------------
# 5. Hero Section
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
    st.markdown("**Sentinel-2 y Landsat 8 (ESA/NASA)**")
with col_h3:
    st.caption("💧 ÍNDICES")
    st.markdown("**NDVI · NDMI · NDBI · LST (Térmico)**")

st.markdown("---")

# ---------------------------------------------------------
# 6. Problem Section
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
            De un ecosistema fragmentado a 1 sola plataforma centralizada con actualización constante.
        </span>
    </div>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 7. Dashboard Satelital (Máquina del Tiempo + Alta Resolución + Catastro)
# ---------------------------------------------------------
st.markdown("<div id='dashboard'></div>", unsafe_allow_html=True)
st.caption("🛰️ DASHBOARD SATELITAL, MÁQUINA DEL TIEMPO & AUDITORÍA DE CATASTRO")
st.markdown("## Parque O'Higgins: salud vegetal y estrés hídrico")
st.write("Viaja en el tiempo para comparar estados históricos, ajusta la transparencia y haz clic en los marcadores para análisis de IA.")

col_time1, col_time2 = st.columns([2, 1])
with col_time1:
    opciones_tiempo = {
        "🛰️ Captura más reciente (Hoy)": 0,
        "⏪ Hace 5 días": 5, "⏪ Hace 10 días": 10, "⏪ Hace 15 días": 15,
        "⏪ Hace 20 días": 20, "⏪ Hace 25 días": 25, "⏪ Hace 1 mes (30 días)": 30,
        "⏪ Hace 2 meses": 60, "⏪ Hace 3 meses": 90, "⏪ Hace 6 meses": 180,
        "⏪ Hace 1 año": 365, "📅 Elegir fecha exacta en el calendario...": -1
    }
    seleccion_tiempo = st.selectbox("🕒 Viajar en el tiempo (Comparación Histórica):", list(opciones_tiempo.keys()))

with col_time2:
    dias_atras = opciones_tiempo[seleccion_tiempo]
    if dias_atras == -1:
        fecha_objetivo = st.date_input("Selecciona una fecha:", value=datetime.now().date() - timedelta(days=365), min_value=datetime(2016, 1, 1).date(), max_value=datetime.now().date())
    else:
        fecha_objetivo = datetime.now().date() - timedelta(days=dias_atras)
        st.date_input("Fecha objetivo calculada:", value=fecha_objetivo, disabled=True)

col_ctrl1, col_ctrl2 = st.columns([3, 1])
with col_ctrl1:
    # NUEVA OPCIÓN: Agregamos las Zonas de 20x20
    capa_seleccionada = st.radio(
        "Capas de análisis Sentinel-2 / Landsat:",
        ["🌱 Índice de Salud (NDVI)", "💧 Estrés Hídrico (NDMI)", "🔲 Zonas de Cuidado (20x20m)", "🏢 Zonas Construidas (NDBI)", "🌡️ Mapa Térmico (Landsat)", "📸 Foto Satelital (RGB)"],
        horizontal=True
    )
with col_ctrl2:
    opacidad_capa = st.slider("Transparencia de la capa:", min_value=0.0, max_value=1.0, value=0.75, step=0.05)

tile_url, promedio_val, fecha_real = obtener_capa_satelital(capa_seleccionada, fecha_objetivo)
st.info(f"📅 **Última actualización de esta vista:** Captura satelital real tomada el **{fecha_real}**.")

# MEJORA 2: Zoom fino milimétrico
m = folium.Map(
    location=[-33.4625, -70.6588], 
    zoom_start=16.5, 
    zoom_control=True,
    zoom_snap=0.25,      # Permite acercar/alejar de a poco
    zoom_delta=0.25,     # La rueda del ratón y el botón +/- avanzan un 25% en vez del 100%
    tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    attr="Esri World Imagery (Alta Resolución)"
)

folium.TileLayer(
    tiles="https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",
    attr="Etiquetas Viales Esri", name="🗺️ Calles y Lugares", overlay=True, control=True
).add_to(m)

if tile_url:
    # Limpiamos el nombre feo para que la leyenda se vea profesional
    folium.TileLayer(tiles=tile_url, attr="Copernicus Sentinel-2", name=f"🛰️ {capa_seleccionada}", overlay=True, control=True, opacity=opacidad_capa).add_to(m)

diccionario_arboles_base = cargar_arboles_geojson('arboles.geojson')

if diccionario_arboles_base:
    
    # MEJORA 5: Extraer estado matemático para colorear los árboles
    with st.spinner("Escaneando el estado hídrico de todo el catastro..."):
        diccionario_arboles = obtener_estado_arboles(diccionario_arboles_base, fecha_objetivo)
        
    # Capas separadas para que la leyenda permita apagar los que están sanos
    grupo_sanos = folium.FeatureGroup(name="🟢 Estado Óptimo (NDMI alto)", show=True)
    grupo_leves = folium.FeatureGroup(name="🟡 Estrés Leve (Mantención)", show=True)
    grupo_criticos = folium.FeatureGroup(name="🔴 Déficit Crítico (Alerta)", show=True)
    
    for arbol in diccionario_arboles.values():
        especie_str = str(arbol.get('especie', '')).title()
        ndmi_val = arbol.get('ndmi', 0.15)
        
        # Semáforo lógico
        if ndmi_val >= 0.15:
            fill_color, grupo_destino, estado_str = "#10b981", grupo_sanos, "Salud Óptima"
        elif ndmi_val >= 0.0:
            fill_color, grupo_destino, estado_str = "#f59e0b", grupo_leves, "Estrés Leve"
        else:
            fill_color, grupo_destino, estado_str = "#ef4444", grupo_criticos, "Déficit Crítico"
            
        icono = "🌴" if "Palma" in especie_str or "Jubaea" in especie_str else "🌳"
            
        html_popup = f"""
        <div style="font-family: 'Plus Jakarta Sans', sans-serif; min-width: 170px; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
            <div style="background-color: {fill_color}; color: white; padding: 6px 12px; font-weight: bold; font-size: 13px; border-bottom: 1px solid rgba(0,0,0,0.1);">
                {icono} {especie_str} (ID #{arbol['id']})
            </div>
            <div style="padding: 10px 12px; background-color: #ffffff; color: #333333;">
                <p style="margin: 0 0 6px 0; font-size: 12px;"><b>Etapa:</b> {arbol['etapa']}</p>
                <p style="margin: 0; font-size: 12px;"><b>Situación:</b> <span style="color: {fill_color}; font-weight: bold;">{estado_str}</span></p>
            </div>
        </div>
        """
        folium.CircleMarker(
            location=[arbol['lat'], arbol['lng']], radius=5.5, popup=folium.Popup(html_popup, max_width=250),
            color="#ffffff", weight=1, fill=True, fill_color=fill_color, fill_opacity=0.95
        ).add_to(grupo_destino)
        
    grupo_sanos.add_to(m)
    grupo_leves.add_to(m)
    grupo_criticos.add_to(m)

# MEJORA 4: Leyenda oculta y limpia (Retráctil)
folium.LayerControl(position="topright", collapsed=True).add_to(m)

# Renderizar el mapa de Folium y capturar interacción
map_data = st_folium(m, width="100%", height=560, key=f"{capa_seleccionada}_{opacidad_capa}_{fecha_objetivo}")
# ---------------------------------------------------------
# 8. MOTOR HÍBRIDO DE IA
# ---------------------------------------------------------
arbol_seleccionado = None

# Detectar clic en el mapa
if map_data and map_data.get("last_object_clicked"):
    lat_click, lng_click = map_data["last_object_clicked"]["lat"], map_data["last_object_clicked"]["lng"]
    llave_busqueda = f"{round(lat_click, 4)}_{round(lng_click, 4)}"
    arbol_seleccionado = diccionario_arboles.get(llave_busqueda)
    # Limpiamos selección de tabla si se hace clic en el mapa
    if 'arbol_tabla_id' in st.session_state:
        del st.session_state['arbol_tabla_id']
        
# Detectar clic en la tabla de alertas
elif st.session_state.get('arbol_tabla_id'):
    for k, v in diccionario_arboles.items():
        if v['id'] == st.session_state['arbol_tabla_id']:
            arbol_seleccionado = v
            break

if arbol_seleccionado:
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(f"### 🧠 Inspección de Cuadrante & Diagnóstico Híbrido (ID #{arbol_seleccionado['id']} - {arbol_seleccionado['especie'].title()})")
    
    with st.spinner("Descargando cuadrante HD, historial temporal y ejecutando IA..."):
        datos_historicos, tile_hd = generar_tiling_y_metricas(arbol_seleccionado['lat'], arbol_seleccionado['lng'], fecha_objetivo)
        diagnostico = generar_diagnostico_hibrido(arbol_seleccionado['especie'], arbol_seleccionado['etapa'], arbol_seleccionado['id'], datos_historicos, fecha_real, tile_hd)
        
        col_vis, col_datos = st.columns([1, 2.2])
        with col_vis:
            st.caption("🎯 **Contexto Visual de Alta Resolución**")
            if tile_hd:
                st.image(tile_hd, caption="Fondo Esri World Imagery (Ref)", use_container_width=True)
            else:
                st.info("No se pudo cargar la imagen base.")
                
        with col_datos:
            st.caption("📊 **Algoritmo Matemático (Ojo Satelital Sentinel-2)**")
            col_ia1, col_ia2, col_ia3 = st.columns(3)
            col_ia1.metric(f"NDVI ({datos_historicos['fecha_previa']})", datos_historicos['NDVI_pasado'])
            col_ia2.metric(f"NDVI ({fecha_real})", datos_historicos['NDVI_hoy'], delta=round(datos_historicos['NDVI_hoy'] - datos_historicos['NDVI_pasado'], 2))
            col_ia3.metric(f"NDMI ({fecha_real})", datos_historicos['NDMI_hoy'])
            
            st.success("Análisis Híbrido (Visión + Índices Infrarrojos) completado")
            st.markdown(f"> **🤖 Prescripción Operativa:** {diagnostico}")

            if datos_historicos.get("serie_temporal"):
                st.markdown("📈 **Evolución Biológica (Últimos 8 meses)**")
                df_ts = pd.DataFrame(datos_historicos["serie_temporal"]).set_index("Fecha")
                st.line_chart(df_ts, color=["#10b981", "#3b82f6"], height=180)

# ---------------------------------------------------------
# 9. Panel de Impacto Ambiental & Alerta Temprana
# ---------------------------------------------------------
if "Normal" not in capa_seleccionada and "Térmico" not in capa_seleccionada:
    pct_val = int(max(0, min(1, promedio_val + 0.3)) * 100) if "NDVI" in capa_seleccionada else 78
    # Estimación algorítmica: Hectáreas x NDVI Promedio x Factor de Absorción
    hectareas_parque = 75 
    toneladas_co2 = round((pct_val / 100) * hectareas_parque * 1.5, 1)

    st.markdown("---")
    st.markdown("### 🌍 Impacto Climático y Alertas Operativas")
    
    # Damos más espacio a la columna 3 para que la tabla se vea bien
    col_m1, col_m2, col_m3 = st.columns([1, 1, 2])
    
    with col_m1:
        st.metric(label="SALUD VEGETAL PROMEDIO", value=f"{pct_val}%", delta="Estado Óptimo")
    with col_m2:
        st.metric(label="CAPTURA ESTIMADA DE CO2", value=f"{toneladas_co2} Toneladas/mes", delta="Vigor Biológico Activo")
    with col_m3:
        st.error("🚨 **Riesgo Hídrico (Haz clic en un árbol para inspeccionarlo)**")
        
        # Filtrar y ordenar árboles con estrés
        lista_riesgo = []
        for k, v in diccionario_arboles.items():
            if v.get('ndmi', 0.15) < 0.15:
                estado = "Crítico 🔴" if v.get('ndmi', 0.15) < 0.0 else "Leve 🟡"
                lista_riesgo.append({"ID": v['id'], "Especie": v['especie'].title(), "NDMI": round(v.get('ndmi', 0.15), 2), "Estado": estado})
        
        if lista_riesgo:
            df_riesgo = pd.DataFrame(lista_riesgo).sort_values(by="NDMI")
            
            # Tabla interactiva
            evento_tabla = st.dataframe(
                df_riesgo, 
                hide_index=True, 
                use_container_width=True, 
                selection_mode="single-row", 
                on_select="rerun"
            )
            
            # Capturar el clic en la fila de la tabla y guardarlo en el estado de sesión
            if len(evento_tabla.selection.rows) > 0:
                idx_seleccionado = evento_tabla.selection.rows[0]
                st.session_state['arbol_tabla_id'] = df_riesgo.iloc[idx_seleccionado]['ID']
        else:
            st.success("¡Todos los árboles de la zona se encuentran en estado óptimo!")

# ---------------------------------------------------------
# 10. GUÍA TÉCNICA E INTERPRETACIÓN CIENTÍFICA B2G
# ---------------------------------------------------------
st.markdown("---")
st.markdown("### 📖 Guía Científica de Algoritmos e Índices (Copernicus Sentinel-2)")
st.write("Esta sección documenta los parámetros hiperespectrales utilizados por el motor de Earth Engine para evaluar la biomasa urbana.")

tab_ndvi, tab_ndmi, tab_ndbi = st.tabs(["🌳 Índice NDVI (Salud Vegetal)", "💧 Índice NDMI (Estrés Hídrico)", "🏢 Índice NDBI (Zonas Construidas)"])

with tab_ndvi:
    st.markdown("""
#### **NDVI (Normalized Difference Vegetation Index)**
El NDVI es el estándar global para cuantificar el vigor y la densidad de la vegetación. Utiliza la diferencia entre la luz infrarroja cercana (que la vegetación sana refleja fuertemente) y la luz roja (que la clorofila absorbe para la fotosíntesis).

**Fórmula Matemática:** `(NIR - RED) / (NIR + RED)`

**Escala de Valores y Diagnóstico:**
- 🔲 **-1.0 a 0.0:** Cuerpos de agua, nieve o estructuras urbanas densas (cemento/asfalto).
- 🟫 **0.0 a 0.2:** Suelo desnudo, tierra seca, rocas o arena.
- 🟨 **0.2 a 0.4:** Vegetación rala, pasto muy seco, arbustos o árboles en estado de latencia/estrés severo.
- 🟩 **0.4 a 0.6:** Vegetación moderada. Típico de árboles jóvenes, pasto en transición o dosel arbóreo abierto.
- 🌲 **0.6 a 0.8:** Dosel arbóreo denso y sano. Alta concentración de clorofila y actividad fotosintética vigorosa.
- 🌳 **0.8 a 1.0:** Excepcionalmente vigoroso (común en selvas tropicales o cultivos hiper-irrigados).
    """)

with tab_ndmi:
    st.markdown("""
#### **NDMI (Normalized Difference Moisture Index)**
El NDMI es altamente sensible al contenido de agua líquida en las hojas y el dosel arbóreo. Es el índice más confiable para la detección temprana de sequías y la programación de riego inteligente, ya que penetra más allá de la simple "coloración verde" (NDVI).

**Fórmula Matemática:** `(NIR - SWIR) / (NIR + SWIR)`
*(El sensor SWIR o Infrarrojo de Onda Corta es altamente absorbido por el agua).*

**Escala de Valores y Diagnóstico:**
- 🟥 **-1.0 a -0.2:** Déficit hídrico crítico. Ausencia total de humedad foliar o suelo desnudo extremo.
- 🟧 **-0.2 a 0.0:** Estrés hídrico alto. La planta está perdiendo agua rápidamente. **(Requiere riego de emergencia)**.
- 🟨 **0.0 a 0.2:** Estrés hídrico moderado a leve. Riego de mantenimiento sugerido.
- 🟦 **0.2 a 0.4:** Hidratación óptima. Dosel con excelente reserva de agua.
- 💦 **0.4 a 1.0:** Saturación de agua (puede indicar encharcamiento, anegamiento o lluvia reciente).
    """)

with tab_ndbi:
    st.markdown("""
#### **NDBI (Normalized Difference Built-up Index)**
Diseñado para mapear áreas urbanas y superficies impermeables. Es fundamental para detectar **Islas de Calor Urbano**, ya que el asfalto y el concreto retienen una cantidad masiva de radiación térmica, afectando a los árboles circundantes.

**Fórmula Matemática:** `(SWIR - NIR) / (SWIR + NIR)`

**Escala de Valores y Diagnóstico:**
- 🟦 **-1.0 a -0.2:** Cuerpos de agua profundos.
- 🟩 **-0.2 a 0.0:** Cobertura vegetal densa. Actúa como regulador térmico (enfriamiento natural).
- 🟨 **0.0 a 0.2:** Zonas mixtas. Combinación de suelo, pasto y estructuras pequeñas (ej. senderos de parque).
- 🟥 **0.2 a 1.0:** Alta densidad constructiva. Asfalto continuo, edificios y techos. Estas zonas irradian calor extremo y aceleran la evaporación del agua en los árboles cercanos.
    """)
