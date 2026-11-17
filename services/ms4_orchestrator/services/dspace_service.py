import os
import json
import glob
try:
    from clients.dspace_auth_client import DSpaceAuthClient
except ImportError:
    from services.ms4_orchestrator.clients.dspace_auth_client import DSpaceAuthClient
import asyncio

def normalize_license(raw_license: str = None) -> str | None:
    """Normaliza identificadores y URLs de licencias a formato estándar legible (ej: cc-by)."""
    if not raw_license:
        return None
    raw = str(raw_license).strip()
    if raw in ["No disponible", "", "None", "null", "undefined"]:
        return None
    low = raw.lower()
    if "by-nc-nd" in low:
        return "cc-by-nc-nd"
    if "by-nc-sa" in low:
        return "cc-by-nc-sa"
    if "by-nc" in low:
        return "cc-by-nc"
    if "by-sa" in low:
        return "cc-by-sa"
    if "by-nd" in low:
        return "cc-by-nd"
    if "cc0" in low or "zero" in low:
        return "cc0"
    if "publicdomain" in low or "public domain" in low or "public-domain" in low:
        return "public-domain"
    if "creativecommons.org" in low or "creative commons" in low or low.startswith("cc"):
        if "by" in low:
            return "cc-by"
        return "cc-by"
    return raw

class DSpaceService:
    def __init__(self):
        self.client = DSpaceAuthClient()
        self.token = None # Aquí guardaremos el token para no pedirlo en cada consulta

    @property
    def cache_dir(self) -> str:
        """
        Retorna la ruta al directorio de caché de DSpace.
        Prioriza la variable de entorno DSPACE_CACHE_DIR,
        luego busca en la raíz del proyecto o en el directorio actual.
        Asegura que el directorio exista en disco.
        """
        env_dir = os.environ.get("DSPACE_CACHE_DIR")
        if env_dir:
            path = os.path.abspath(env_dir)
        else:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            repo_root = os.path.abspath(os.path.join(current_dir, "..", "..", ".."))
            root_cache = os.path.join(repo_root, "cache_dspace")
            
            if os.path.exists("cache_dspace"):
                path = os.path.abspath("cache_dspace")
            elif os.path.exists(root_cache):
                path = root_cache
            elif os.path.exists(os.path.join(repo_root, "docker-compose.yml")):
                path = root_cache
            else:
                path = os.path.abspath("cache_dspace")

        if not os.path.exists(path):
            os.makedirs(path, exist_ok=True)
        return path

    def get_cache_stats(self) -> dict:
        """Retorna estadísticas sobre los archivos y tamaño de la caché en disco."""
        d = self.cache_dir
        if not os.path.exists(d):
            return {
                "cache_dir": d,
                "total_files": 0,
                "page_files": 0,
                "item_files": 0,
                "size_bytes": 0
            }
        
        page_files = glob.glob(os.path.join(d, "page_*.json"))
        item_files = glob.glob(os.path.join(d, "item_*.json"))
        all_files = glob.glob(os.path.join(d, "*.json"))
        total_size = sum(os.path.getsize(f) for f in all_files if os.path.exists(f))
        
        return {
            "cache_dir": d,
            "total_files": len(all_files),
            "page_files": len(page_files),
            "item_files": len(item_files),
            "size_bytes": total_size
        }

    def clear_cache(self, clear_pages: bool = True, clear_items: bool = True) -> dict:
        """Limpia archivos de caché en disco para forzar refresco."""
        d = self.cache_dir
        deleted = 0
        if os.path.exists(d):
            patterns = []
            if clear_pages:
                patterns.append("page_*.json")
            if clear_items:
                patterns.append("item_*.json")
            if clear_pages and clear_items:
                patterns.append("*.json")
                
            for pat in set(patterns):
                for f in glob.glob(os.path.join(d, pat)):
                    try:
                        os.remove(f)
                        deleted += 1
                    except Exception:
                        pass
        return {"deleted_files": deleted, "cache_dir": d}
        
    async def _ensure_authenticated(self):
        """Helper para autenticarse solo si no tenemos un token activo."""
        if not self.token:
            self.token = await self.client.authenticate()
            if not self.token:
                raise Exception("No se pudo obtener el token de DSpace. Revisa tus credenciales.")
    
    async def get_all_items(self, page: int = 0, size: int = 20, use_cache: bool = True):
        """
        Obtiene ítems del repositorio con paginación.
        Implementa una caché local en disco para no saturar la API ni la RAM y consumir datos más rápido.
        """
        cache_dir = self.cache_dir
        cache_file = os.path.join(cache_dir, f"page_{page}_size_{size}.json")
        
        # 1. Intentamos leer desde la caché en disco
        if use_cache and os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
                
        await self._ensure_authenticated()
        
        # Le pasamos parámetros de paginación y filtros al cliente
        params = {
            "page": page,
            "size": size,
            "f.entityType": "Publication,equals" # Filtramos para que solo traiga publicaciones reales
        }
        
        # Utilizamos el método get_items del cliente (apunta a /discover/search/objects)
        data = await self.client.get_items(self.token, query_params=params)
        
        # La API de Discover tiene una estructura anidada diferente a /core/items
        search_result = data.get("_embedded", {}).get("searchResult", {})
        
        # Obtenemos los ítems crudos (objects)
        raw_items = search_result.get("_embedded", {}).get("objects", [])
        
        # Parseamos y limpiamos los ítems
        items = [self._parse_item(item) for item in raw_items]
        
        result = {
            "items": items,
            "page_info": search_result.get("page", {}) # Info útil de total de páginas, etc.
        }
        
        # 2. Guardamos el resultado en disco
        if use_cache:
            try:
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                # Cachear individualmente por UUID para acelerar consultas puntuales
                for itm in items:
                    u = itm.get("uuid")
                    if u:
                        item_file = os.path.join(cache_dir, f"item_{u}.json")
                        with open(item_file, "w", encoding="utf-8") as f_item:
                            json.dump(itm, f_item, ensure_ascii=False, indent=2)
            except Exception:
                pass
                
        return result

    def _parse_item(self, item: dict) -> dict:
        """Extrae de forma limpia los metadatos más importantes de un registro de DSpace."""
        indexable_object = item.get("_embedded", {}).get("indexableObject", {})
        metadata = indexable_object.get("metadata", {})
        
        # Función auxiliar para sacar el primer valor de una lista de metadatos de DSpace
        def get_metadata_value(field: str, default: str = None):
            values = metadata.get(field, [])
            if values and len(values) > 0:
                val = values[0].get("value")
                # Verificamos que 'val' no sea nulo ni un texto en blanco
                if val is not None and str(val).strip():
                    return str(val).strip()
            return default

        # Función auxiliar para sacar todos los valores de una lista de metadatos (útil para palabras clave/subjects)
        def get_metadata_values_list(field: str):
            values = metadata.get(field, [])
            return [str(v.get("value")).strip() for v in values if v.get("value") is not None and str(v.get("value")).strip()]

        title_candidate = get_metadata_value("dc.title") or indexable_object.get("name") or "Sin título"
        
        # Fuentes de financiamiento (DSpace-CRIS / OpenAIRE / Dublin Core)
        funding_fields = [
            "dc.description.sponsorship",
            "oairecerif.funding",
            "oairecerif.funder",
            "oaire.fundingStream",
            "dc.contributor.funder",
            "crisfund.funding",
            "project.funding"
        ]
        funding_list = []
        for ff in funding_fields:
            vals = get_metadata_values_list(ff)
            if vals:
                funding_list.extend(vals)

        # Derechos de acceso (openAccess, restrictedAccess, etc.)
        rights_candidate = (
            get_metadata_value("dc.rights") or
            get_metadata_value("oaire.openAccess") or
            get_metadata_value("dc.rights.accessRights") or
            None
        )

        # Licencia (ej. cc-by, URL Creative Commons, etc.)
        raw_license_candidate = (
            get_metadata_value("dc.rights.license") or
            get_metadata_value("oaire.licenseCondition") or
            get_metadata_value("dc.rights.uri") or
            get_metadata_value("cclicense.uri") or
            None
        )

        # Si dc.rights contiene la licencia en lugar del estado de acceso
        if not raw_license_candidate and rights_candidate and any(k in rights_candidate.lower() for k in ["creative", "cc-", "cc ", "by", "license"]):
            raw_license_candidate = rights_candidate
            if "open" not in rights_candidate.lower():
                rights_candidate = None

        license_candidate = normalize_license(raw_license_candidate)

        return {
            "uuid": indexable_object.get("id") or indexable_object.get("uuid"),
            "title": title_candidate,
            "abstract": get_metadata_value("dc.description.abstract", "No disponible"),
            "doi": get_metadata_value("dc.identifier.doi", "No disponible"),
            "type": get_metadata_value("dc.type", "No disponible"),
            "oaire_resourcetype": get_metadata_value("oaire.resourceType", "No disponible"),
            "keywords": get_metadata_values_list("dc.subject"), # Puede tener múltiples valores
            "funding": funding_list, # Lista de entidades o proyectos de financiamiento
            "rights": rights_candidate, # Derechos de acceso
            "license": license_candidate, # Licencia (ej. cc-by)
            "uri": get_metadata_value("dc.identifier.uri"), # Link público usualmente
            "all_metadata": metadata
        }
        
    async def get_metadata(self, identifier: str, use_cache: bool = True):
        """
        Obtiene los metadatos de un ID en específico (UUID).
        Implementa caché en disco para respuesta inmediata.
        Si use_cache=True:
          1. Intenta leer 'item_{identifier}.json' desde el cache_dir.
          2. Busca el UUID dentro de los archivos 'page_*.json' cacheados.
          3. Si no está en caché, consulta DSpace y almacena el resultado en caché.
        """
        cache_dir = self.cache_dir
        item_cache_file = os.path.join(cache_dir, f"item_{identifier}.json")
        
        # 1. Intentar leer caché puntual del ítem
        if use_cache and os.path.exists(item_cache_file):
            try:
                with open(item_cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass

        # 2. Intentar buscar en páginas ya cacheadas en disco
        if use_cache and os.path.exists(cache_dir):
            try:
                for page_file in glob.glob(os.path.join(cache_dir, "page_*.json")):
                    with open(page_file, "r", encoding="utf-8") as pf:
                        p_data = json.load(pf)
                        for itm in p_data.get("items", []):
                            if itm.get("uuid") == identifier:
                                # Guardar en caché puntual para la próxima consulta
                                try:
                                    with open(item_cache_file, "w", encoding="utf-8") as itm_f:
                                        json.dump(itm, itm_f, ensure_ascii=False, indent=2)
                                except Exception:
                                    pass
                                return itm
            except Exception:
                pass

        await self._ensure_authenticated()
        
        size = 100
        params = {
            "page": 0,
            "size": size,
            "dsoType": "item"
        }
        
        # Función auxiliar para buscar el UUID dentro de los raw items de una página
        def encontrar_raw_item(raw_items_list):
            for raw_item in raw_items_list:
                indexable_object = raw_item.get("_embedded", {}).get("indexableObject", {})
                item_id = indexable_object.get("id")
                item_uuid = indexable_object.get("uuid")
                if identifier in (item_id, item_uuid):
                    return raw_item
            return None
            
        # 1. Buscar en la primera página y obtener el total de páginas
        data = await self.client.get_items(self.token, query_params=params)
        search_result = data.get("_embedded", {}).get("searchResult", {})
        raw_items = search_result.get("_embedded", {}).get("objects", [])
        
        encontrado_raw = encontrar_raw_item(raw_items)
        if encontrado_raw:
            item_data = self._parse_item(encontrado_raw)
            item_data["all_metadata"] = encontrado_raw.get("_embedded", {}).get("indexableObject", {}).get("metadata", {})
            if use_cache:
                try:
                    with open(item_cache_file, "w", encoding="utf-8") as f:
                        json.dump(item_data, f, ensure_ascii=False, indent=2)
                except Exception:
                    pass
            return item_data
            
        page_info = search_result.get("page", {})
        total_pages = page_info.get("totalPages", 1)
        
        # 2. Si hay más páginas, buscamos en paralelo
        if total_pages > 1:
            max_concurrent = 10 # Buscamos rápido de a 10 páginas
            semaphore = asyncio.Semaphore(max_concurrent)
            
            async def buscar_en_pagina(page_num):
                async with semaphore:
                    try:
                        p = {"page": page_num, "size": size, "dsoType": "item"}
                        d = await self.client.get_items(self.token, query_params=p)
                        sr = d.get("_embedded", {}).get("searchResult", {})
                        r_items = sr.get("_embedded", {}).get("objects", [])
                        return encontrar_raw_item(r_items)
                    except Exception as e:
                        print(f"Error procesando página {page_num} buscando UUID: {e}")
                        return None

            # Lanzamos tareas para las páginas restantes
            tareas = [asyncio.create_task(buscar_en_pagina(p)) for p in range(1, total_pages)]
            
            # as_completed nos permite reaccionar apenas una tarea termine
            for tarea in asyncio.as_completed(tareas):
                resultado_tarea = await tarea
                if resultado_tarea:
                    # Encontramos el ítem, cancelamos el resto de las tareas para no saturar
                    for t in tareas:
                        if not t.done():
                            t.cancel()
                    item_data = self._parse_item(resultado_tarea)
                    item_data["all_metadata"] = resultado_tarea.get("_embedded", {}).get("indexableObject", {}).get("metadata", {})
                    if use_cache:
                        try:
                            with open(item_cache_file, "w", encoding="utf-8") as f:
                                json.dump(item_data, f, ensure_ascii=False, indent=2)
                        except Exception:
                            pass
                    return item_data
                    
        return {"error": f"No se encontró ningún registro con el UUID {identifier} en todo el repositorio."}

    async def count_missing_metadata_optimized(self, size: int = 100, max_concurrent: int = 5, save_to_db: bool = False, db = None, use_cache: bool = True):
        """
        Recorre el repositorio en paralelo para máxima velocidad.
        Cuenta ítems sin abstract y sin DOI dentro de valid_resource_types.
        Opcionalmente guarda el histórico de métricas y la cola de enriquecimiento en base de datos.
        Aprovecha la caché local en disco para acelerar consultas recurrentes.
        """
        print("Iniciando escaneo optimizado de metadatos faltantes...")
        
        # 1. Petición inicial
        resultado_inicial = await self.get_all_items(page=0, size=size, use_cache=use_cache)
        page_info = resultado_inicial.get("page_info", {})
        total_pages = page_info.get("totalPages", 1)
        
        print(f"Total de páginas a procesar: {total_pages} (a {size} ítems por página)")

        total_revisados = 0
        total_valid_resource_types = 0
        total_missing_title= 0
        total_missing_abs = 0
        total_no_abstract = 0
        total_missing_abs_org_art = 0
        total_missing_doi = 0
        total_missing_subjects = 0
        total_type_journal_Article = 0
        total_uuids_missing_abs_org_art = []
        total_uuids_pub_sin_doi_sin_abs = []
        total_distinct_oaire_types = set()
        total_pub_sin_doi_sin_abs = 0
        total_sin_abstract_con_doi = 0
        total_uuids_sin_abstract_con_doi = []
        total_sin_doi_ni_abstract = 0
        total_uuids_sin_doi_ni_abstract = []
        total_candidatos_enriquecimiento = []

        valid_resource_types = {
            "patente",
            "texto",
            "texto::artículo preliminar",
            "texto::contribución de congreso::actas de congreso::comunicación de congreso",
            #"texto::contribución de congreso::comunicación no publicada en actas de congreso",
            #"texto::contribución de congreso::presentación de congreso",
            "texto::informe",
            "texto::informe::estudio clínico",
            "texto::informe::informe técnico",
            "texto::libro::capítulo de libro",
            "texto::ponencia",
            "texto::revista::artículo",
            "texto::revista::artículo::artículo de revisión",
            "texto::revista::artículo::artículo original"
        }

        def procesar_items(items):
            revisados_pag = len(items)
            valid_resource_types_pag = 0
            missing_title_pag = 0
            missing_abs_pag = 0
            no_abstract_pag = 0
            missing_doi_pag = 0
            missing_subjects_pag = 0
            type_journal_Article_pag = 0
            missing_abs_org_art = 0
            pub_sin_doi_sin_abs = 0
            uuids_missing_abs_org_art = []
            uuids_pub_sin_doi_sin_abs = []
            distinct_oaire_pag = set()
            sin_abstract_con_doi_pag = 0
            uuids_sin_abstract_con_doi_pag = []
            sin_doi_ni_abstract_pag = 0
            uuids_sin_doi_ni_abstract_pag = []
            candidatos_pag = []
            
            for item in items:
                oaire_val = item.get("oaire_resourcetype")
                if oaire_val and oaire_val not in valid_resource_types:
                    distinct_oaire_pag.add(oaire_val)
                    
                # Solo procesar métricas y salidas para ítems dentro de valid_resource_types
                if oaire_val not in valid_resource_types:
                    continue

                valid_resource_types_pag += 1
                uuid = item.get("uuid")

                # Abstract
                abs_val = item.get("abstract")
                is_missing_abs = abs_val in ["No disponible", "", "Sin resumen"]
                is_no_abs_available = abs_val == "[No abstract available]"
                is_any_missing_abs = is_missing_abs or is_no_abs_available

                if is_missing_abs:
                    missing_abs_pag += 1
                    missing_abs_org_art += 1
                    uuids_missing_abs_org_art.append(uuid)

                if is_no_abs_available:
                    no_abstract_pag += 1

                # DOI
                doi_val = item.get("doi")
                is_missing_doi = doi_val in ["No disponible", "", None]
                has_doi = not is_missing_doi

                if is_missing_doi:
                    missing_doi_pag += 1

                # Title
                title_val = item.get("title")
                is_missing_title = title_val in ["No disponible", "", "Sin título", None]
                if is_missing_title:
                    missing_title_pag += 1

                # Keywords / Subjects
                keywords_val = item.get("keywords") or []
                is_missing_keywords = not keywords_val or len(keywords_val) == 0
                if is_missing_keywords:
                    missing_subjects_pag += 1

                # Funding / Financiamiento
                funding_val = item.get("funding") or []
                is_missing_funding = not funding_val or len(funding_val) == 0

                # Rights / Derechos de acceso
                rights_val = item.get("rights")
                is_missing_rights = not rights_val or rights_val in ["No disponible", "", None]

                # License / Licencia
                license_val = item.get("license")
                is_missing_license = not license_val or license_val in ["No disponible", "", None]

                # Type
                if item.get("type") == "text::journal::journal article":
                    type_journal_Article_pag += 1

                # Sin abstract con DOI (dentro de valid_resource_types)
                if is_any_missing_abs and has_doi:
                    sin_abstract_con_doi_pag += 1
                    uuids_sin_abstract_con_doi_pag.append(uuid)

                # Sin DOI ni abstract (dentro de valid_resource_types)
                if is_any_missing_abs and is_missing_doi:
                    sin_doi_ni_abstract_pag += 1
                    uuids_sin_doi_ni_abstract_pag.append(uuid)
                    pub_sin_doi_sin_abs += 1
                    uuids_pub_sin_doi_sin_abs.append(uuid)

                # Construcción integral de falencias de metadatos detectadas
                falencias = []
                if is_any_missing_abs and is_missing_doi:
                    falencias.append("SIN_DOI_NI_ABSTRACT")
                elif is_any_missing_abs and has_doi:
                    falencias.append("SIN_ABSTRACT_CON_DOI")
                elif is_any_missing_abs:
                    falencias.append("SIN_ABSTRACT")
                elif is_missing_doi:
                    falencias.append("SIN_DOI")

                if is_missing_keywords:
                    falencias.append("SIN_PALABRAS_CLAVE")
                if is_missing_funding:
                    falencias.append("SIN_FINANCIAMIENTO")
                if is_missing_rights:
                    falencias.append("SIN_DERECHOS_ACCESO")
                if is_missing_license:
                    falencias.append("SIN_LICENCIA")

                # Si le falta cualquiera de los metadatos analizados, es candidato para enriquecimiento
                if falencias:
                    candidatos_pag.append({
                        "dspace_uuid": uuid,
                        "doi": doi_val if has_doi else None,
                        "titulo": title_val if not is_missing_title else None,
                        "tipo_recurso": oaire_val,
                        "tipo_falencia": ", ".join(falencias),
                        "derechos_acceso": rights_val if not is_missing_rights else None,
                        "licencia": license_val if not is_missing_license else None,
                        "resumen_original": abs_val if not is_any_missing_abs else None
                    })
                    
            return (
                revisados_pag, missing_title_pag, no_abstract_pag, missing_abs_pag, missing_abs_org_art,
                missing_doi_pag, missing_subjects_pag, type_journal_Article_pag, uuids_missing_abs_org_art,
                distinct_oaire_pag, pub_sin_doi_sin_abs, uuids_pub_sin_doi_sin_abs, sin_abstract_con_doi_pag,
                uuids_sin_abstract_con_doi_pag, sin_doi_ni_abstract_pag, uuids_sin_doi_ni_abstract_pag,
                valid_resource_types_pag, candidatos_pag
            )

        # Procesamos la página 0
        (
            rev, miss_title, no_abstract_pag, miss_abs, miss_abs_org_art, miss_doi, miss_subjects,
            type_journal_Article_pag, uuids_abs_org_art_pag0, dist_oaire_pag0, pub_sin_doi_sin_abs0,
            uuids_pub_sin_doi_sin_abs0, sin_abs_con_doi0, uuids_sin_abs_con_doi0, sin_doi_ni_abstract0,
            uuids_sin_doi_ni_abstract0, valid_res_pag0, cand_pag0
        ) = procesar_items(resultado_inicial.get("items", []))

        total_revisados += rev
        total_valid_resource_types += valid_res_pag0
        total_missing_title+= miss_title
        total_missing_abs += miss_abs
        total_no_abstract += no_abstract_pag
        total_missing_abs_org_art += miss_abs_org_art
        total_missing_doi += miss_doi
        total_missing_subjects += miss_subjects
        total_type_journal_Article += type_journal_Article_pag
        total_uuids_missing_abs_org_art.extend(uuids_abs_org_art_pag0)
        total_distinct_oaire_types.update(dist_oaire_pag0)
        total_pub_sin_doi_sin_abs += pub_sin_doi_sin_abs0
        total_uuids_pub_sin_doi_sin_abs.extend(uuids_pub_sin_doi_sin_abs0)
        total_sin_abstract_con_doi += sin_abs_con_doi0
        total_uuids_sin_abstract_con_doi.extend(uuids_sin_abs_con_doi0)
        total_sin_doi_ni_abstract += sin_doi_ni_abstract0
        total_uuids_sin_doi_ni_abstract.extend(uuids_sin_doi_ni_abstract0)
        total_candidatos_enriquecimiento.extend(cand_pag0)

        if total_pages > 1:
            semaphore = asyncio.Semaphore(max_concurrent)

            async def fetch_and_process_page(page_num):
                async with semaphore:
                    try:
                        print(f"Consultando página {page_num}/{total_pages - 1}...")
                        resultado = await self.get_all_items(page=page_num, size=size, use_cache=use_cache)
                        return procesar_items(resultado.get("items", []))
                    except Exception as e:
                        print(f"Error procesando página {page_num}: {e}")
                        return 0, 0, 0, 0, 0, 0, 0, 0, [], set(), 0, [], 0, [], 0, [], 0, []

            # Tareas para el resto de las páginas
            tareas = [fetch_and_process_page(p) for p in range(1, total_pages)]
            
            resultados_paginas = await asyncio.gather(*tareas)

            # Sumamos resultados
            for (
                rev, miss_title, no_abstract_pag, miss_abs, miss_abs_org_art, miss_doi, miss_subjects,
                type_journal_Article_pag, uuids_abs_org_art_pag, dist_oaire_pag, pub_sin_doi_sin_abs_pag,
                uuids_pub_sin_doi_sin_abs_pag, sin_abs_con_doi_pag, uuids_sin_abs_con_doi_pag,
                sin_doi_ni_abstract_pag, uuids_sin_doi_ni_abstract_pag, valid_res_pag, cand_pag
            ) in resultados_paginas:
                total_revisados += rev
                total_valid_resource_types += valid_res_pag
                total_missing_title+= miss_title
                total_no_abstract += no_abstract_pag
                total_missing_abs += miss_abs
                total_missing_abs_org_art += miss_abs_org_art
                total_missing_doi += miss_doi
                total_missing_subjects += miss_subjects
                total_type_journal_Article += type_journal_Article_pag
                total_uuids_missing_abs_org_art.extend(uuids_abs_org_art_pag)
                total_distinct_oaire_types.update(dist_oaire_pag)
                total_pub_sin_doi_sin_abs += pub_sin_doi_sin_abs_pag
                total_uuids_pub_sin_doi_sin_abs.extend(uuids_pub_sin_doi_sin_abs_pag)
                total_sin_abstract_con_doi += sin_abs_con_doi_pag
                total_uuids_sin_abstract_con_doi.extend(uuids_sin_abs_con_doi_pag)
                total_sin_doi_ni_abstract += sin_doi_ni_abstract_pag
                total_uuids_sin_doi_ni_abstract.extend(uuids_sin_doi_ni_abstract_pag)
                total_candidatos_enriquecimiento.extend(cand_pag)

        total_elements = page_info.get("totalElements")
        if total_elements is not None:
            total_revisados = total_elements

        resultado = {
            "total_revisados": total_revisados,
            "total_valid_resource_types": total_valid_resource_types,
            "total_sin_title": total_missing_title,
            "total_sin_abstract": total_missing_abs,
            "total_no_abstract_disponible": total_no_abstract,
            "total_missing_abs_org_art": total_missing_abs_org_art,
            "total_sin_doi": total_missing_doi,
            "total_sin_subjects": total_missing_subjects,
            "total_pub_sin_doi_sin_abs": total_pub_sin_doi_sin_abs,
            "total_sin_abstract_con_doi": total_sin_abstract_con_doi,
            "total_sin_doi_ni_abstract": total_sin_doi_ni_abstract,        
            "uuids_missing_abs_org_art": total_uuids_missing_abs_org_art,
            "uuids_pub_sin_doi_sin_abs": total_uuids_pub_sin_doi_sin_abs,
            "uuids_sin_abstract_con_doi": total_uuids_sin_abstract_con_doi,
            "uuids_sin_doi_ni_abstract": total_uuids_sin_doi_ni_abstract,
            "total_candidatos_detectados": len(total_candidatos_enriquecimiento),
            "candidatos_enriquecimiento": total_candidatos_enriquecimiento,
        }

        if save_to_db and db is not None:
            guardado_info = self.save_audit_and_queue(resultado, total_candidatos_enriquecimiento, db)
            resultado["db_guardado"] = guardado_info

        return resultado

    def save_audit_and_queue(self, resultado_metricas: dict, candidatos: list, db):
        """
        Persiste el snapshot histórico de métricas en DSpaceMetricsHistory
        y registra los ítems candidatos a enriquecer en DSpaceEnrichmentQueue.
        """
        try:
            from models import DSpaceMetricsHistory, DSpaceEnrichmentQueue
        except ImportError:
            from services.ms4_orchestrator.models import DSpaceMetricsHistory, DSpaceEnrichmentQueue

        # 1. Guardar Snapshot histórico
        snapshot = DSpaceMetricsHistory(
            total_revisados=resultado_metricas.get("total_revisados", 0),
            total_valid_resource_types=resultado_metricas.get("total_valid_resource_types", 0),
            total_sin_title=resultado_metricas.get("total_sin_title", 0),
            total_sin_abstract=resultado_metricas.get("total_sin_abstract", 0),
            total_no_abstract_disponible=resultado_metricas.get("total_no_abstract_disponible", 0),
            total_missing_abs_org_art=resultado_metricas.get("total_missing_abs_org_art", 0),
            total_sin_doi=resultado_metricas.get("total_sin_doi", 0),
            total_sin_subjects=resultado_metricas.get("total_sin_subjects", 0),
            total_pub_sin_doi_sin_abs=resultado_metricas.get("total_pub_sin_doi_sin_abs", 0),
            total_sin_abstract_con_doi=resultado_metricas.get("total_sin_abstract_con_doi", 0),
            total_sin_doi_ni_abstract=resultado_metricas.get("total_sin_doi_ni_abstract", 0),
        )
        db.add(snapshot)
        db.flush()

        # 2. Poblar cola de enriquecimiento evitando duplicados
        candidate_uuids = [c["dspace_uuid"] for c in candidatos if c.get("dspace_uuid")]
        existing_uuids = set()
        for i in range(0, len(candidate_uuids), 1000):
            batch = candidate_uuids[i:i+1000]
            rows = db.query(DSpaceEnrichmentQueue.dspace_uuid).filter(DSpaceEnrichmentQueue.dspace_uuid.in_(batch)).all()
            existing_uuids.update(r[0] for r in rows)

        new_items = []
        seen_uuids = set()
        for c in candidatos:
            uuid = c.get("dspace_uuid")
            if uuid and uuid not in existing_uuids and uuid not in seen_uuids:
                seen_uuids.add(uuid)
                new_items.append(DSpaceEnrichmentQueue(
                    dspace_uuid=uuid,
                    doi=c.get("doi"),
                    titulo=c.get("titulo"),
                    tipo_recurso=c.get("tipo_recurso"),
                    tipo_falencia=c.get("tipo_falencia"),
                    derechos_acceso=c.get("derechos_acceso"),
                    licencia=c.get("licencia"),
                    estado="PENDIENTE",
                    resumen_original=c.get("resumen_original")
                ))
            elif uuid and uuid in existing_uuids and c.get("tipo_falencia"):
                # Actualizar falencias completas en registros existentes que sigan pendientes
                update_fields = {
                    DSpaceEnrichmentQueue.tipo_falencia: c.get("tipo_falencia")
                }
                if c.get("derechos_acceso"):
                    update_fields[DSpaceEnrichmentQueue.derechos_acceso] = c.get("derechos_acceso")
                if c.get("licencia"):
                    update_fields[DSpaceEnrichmentQueue.licencia] = c.get("licencia")
                db.query(DSpaceEnrichmentQueue).filter(
                    DSpaceEnrichmentQueue.dspace_uuid == uuid,
                    DSpaceEnrichmentQueue.estado == "PENDIENTE"
                ).update(update_fields, synchronize_session=False)

        if new_items:
            db.bulk_save_objects(new_items)

        db.commit()

        return {
            "snapshot_id": snapshot.id,
            "total_candidatos_detectados": len(candidatos),
            "nuevos_en_cola": len(new_items),
            "ya_existentes_en_cola": len(seen_uuids & existing_uuids) if seen_uuids else 0
        }