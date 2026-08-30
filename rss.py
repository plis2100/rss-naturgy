import re
import urllib.request
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from urllib.parse import urljoin


BASE_URL = "https://www.naturgy.com"

PAGINA_PRINCIPAL = (
    "https://www.naturgy.com/"
    "sala-de-prensa/"
)

ARCHIVO_RSS = "naturgy.xml"


def limpiar_texto(texto):
    return re.sub(
        r"\s+",
        " ",
        texto or "",
    ).strip()


def descargar_pagina(url):
    solicitud = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,"
                "application/xml;q=0.9,*/*;q=0.8"
            ),
            "Accept-Language": "es-ES,es;q=0.9",
            "Cache-Control": "no-cache",
        },
    )

    with urllib.request.urlopen(
        solicitud,
        timeout=90,
    ) as respuesta:
        return respuesta.read()


def convertir_fecha(texto):
    coincidencia = re.search(
        r"\b(\d{1,2})-(\d{1,2})-(\d{4})\b",
        texto,
    )

    if not coincidencia:
        return None

    dia = int(coincidencia.group(1))
    mes = int(coincidencia.group(2))
    anio = int(coincidencia.group(3))

    try:
        return datetime(
            anio,
            mes,
            dia,
            8,
            0,
            tzinfo=timezone.utc,
        )

    except ValueError:
        return None


def obtener_descripcion(contenedor):
    parrafos = contenedor.find_all("p")

    for parrafo in parrafos:
        descripcion = limpiar_texto(
            parrafo.get_text(" ", strip=True)
        )

        if len(descripcion) >= 60:
            return descripcion[:1000]

    return (
        "Nota de prensa oficial "
        "publicada por Naturgy."
    )


def buscar_contenedor(encabezado):
    contenedor = encabezado

    for _ in range(6):
        if contenedor is None:
            break

        texto = limpiar_texto(
            contenedor.get_text(" ", strip=True)
        )

        if re.search(
            r"\b\d{1,2}-\d{1,2}-\d{4}\b",
            texto,
        ):
            return contenedor

        contenedor = contenedor.parent

    return encabezado.parent


def obtener_noticias():
    contenido = descargar_pagina(
        PAGINA_PRINCIPAL
    )

    soup = BeautifulSoup(
        contenido,
        "html.parser",
    )

    noticias = []
    enlaces_vistos = set()

    for encabezado in soup.find_all(
        ["h2", "h3"]
    ):
        enlace = encabezado.find(
            "a",
            href=True,
        )

        if enlace is None:
            continue

        titulo = limpiar_texto(
            enlace.get_text(" ", strip=True)
        )

        href = limpiar_texto(
            enlace.get("href", "")
        )

        if not titulo or not href:
            continue

        if href.lower().startswith("javascript:"):
            continue

        url = urljoin(
            BASE_URL,
            href,
        )

        url = url.split("#")[0].split("?")[0]

        if "/notas-de-prensa/" not in url:
            continue

        if url in enlaces_vistos:
            continue

        contenedor = buscar_contenedor(
            encabezado
        )

        texto_contenedor = limpiar_texto(
            contenedor.get_text(" ", strip=True)
        )

        fecha = convertir_fecha(
            texto_contenedor
        )

        descripcion = obtener_descripcion(
            contenedor
        )

        enlaces_vistos.add(url)

        noticias.append(
            {
                "titulo": titulo,
                "url": url,
                "fecha": fecha,
                "descripcion": descripcion,
            }
        )

        print(
            f"Noticia encontrada: {titulo}"
        )

    if not noticias:
        raise RuntimeError(
            "No se encontraron noticias "
            "en la sala de prensa de Naturgy"
        )

    noticias.sort(
        key=lambda noticia: (
            noticia["fecha"]
            or datetime(
                1970,
                1,
                1,
                tzinfo=timezone.utc,
            )
        ),
        reverse=True,
    )

    return noticias


def crear_rss(noticias):
    rss = ET.Element(
        "rss",
        {
            "version": "2.0",
            "xmlns:atom": (
                "http://www.w3.org/2005/Atom"
            ),
        },
    )

    canal = ET.SubElement(
        rss,
        "channel",
    )

    ET.SubElement(
        canal,
        "title",
    ).text = "Naturgy – Sala de prensa"

    ET.SubElement(
        canal,
        "link",
    ).text = PAGINA_PRINCIPAL

    ET.SubElement(
        canal,
        "description",
    ).text = (
        "Últimas notas de prensa "
        "oficiales publicadas por Naturgy"
    )

    ET.SubElement(
        canal,
        "language",
    ).text = "es-es"

    ET.SubElement(
        canal,
        "ttl",
    ).text = "60"

    ET.SubElement(
        canal,
        "{http://www.w3.org/2005/Atom}link",
        {
            "href": (
                "https://raw.githubusercontent.com/"
                "plis2100/rss-naturgy/"
                "main/naturgy.xml"
            ),
            "rel": "self",
            "type": "application/rss+xml",
        },
    )

    ET.SubElement(
        canal,
        "lastBuildDate",
    ).text = format_datetime(
        datetime.now(timezone.utc)
    )

    for noticia in noticias:
        elemento = ET.SubElement(
            canal,
            "item",
        )

        ET.SubElement(
            elemento,
            "title",
        ).text = noticia["titulo"]

        ET.SubElement(
            elemento,
            "link",
        ).text = noticia["url"]

        ET.SubElement(
            elemento,
            "guid",
            {"isPermaLink": "true"},
        ).text = noticia["url"]

        ET.SubElement(
            elemento,
            "description",
        ).text = noticia["descripcion"]

        ET.SubElement(
            elemento,
            "source",
            {"url": PAGINA_PRINCIPAL},
        ).text = "Naturgy"

        if noticia["fecha"]:
            ET.SubElement(
                elemento,
                "pubDate",
            ).text = format_datetime(
                noticia["fecha"]
            )

    arbol = ET.ElementTree(rss)

    ET.indent(
        arbol,
        space="  ",
    )

    arbol.write(
        ARCHIVO_RSS,
        encoding="utf-8",
        xml_declaration=True,
    )


def validar_rss():
    archivo = Path(ARCHIVO_RSS)

    if not archivo.exists():
        raise RuntimeError(
            "No se creó naturgy.xml"
        )

    if archivo.stat().st_size < 500:
        raise RuntimeError(
            "naturgy.xml está vacío"
        )

    raiz = ET.parse(archivo).getroot()

    elementos = raiz.findall(
        "./channel/item"
    )

    if not elementos:
        raise RuntimeError(
            "La RSS de Naturgy "
            "no contiene noticias"
        )

    return len(elementos)


def main():
    noticias = obtener_noticias()

    crear_rss(noticias)

    cantidad = validar_rss()

    print(
        f"RSS de Naturgy creada: "
        f"{cantidad} noticias"
    )

    print(
        f"Última noticia: "
        f"{noticias[0]['titulo']}"
    )

    print(
        f"Archivo generado: "
        f"{ARCHIVO_RSS}"
    )


if __name__ == "__main__":
    main()
