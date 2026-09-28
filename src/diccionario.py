# -*- coding: utf-8 -*-
"""
diccionario.py
==============
Diccionario semantico de las 36 variables del dataset: definicion, dominio
esperado y rol analitico. Escrito a mano a partir de la documentacion de
SECOP II; todo lo demas (completitud, cardinalidad, distribuciones) se calcula.

`rol` distingue Identificador / Dimension / Metrica / Enlace, y es lo que
permite decidir que variable sirve para segmentar y cual para medir.
"""
from __future__ import annotations

DICCIONARIO = {
    "id_contrato": dict(
        bloque="Identificación",
        definicion="Identificador único del contrato en SECOP II. Formato 'CO1.PCCNTR.<consecutivo>'.",
        dominio="Cadena con prefijo CO1.PCCNTR. seguido de un consecutivo numérico.",
        rol="Identificador"),
    "nombre_entidad": dict(
        bloque="Entidad contratante",
        definicion="Razón social de la entidad estatal que suscribe el contrato.",
        dominio="Texto libre normalizado por SECOP; alta cardinalidad.",
        rol="Dimensión"),
    "departamento": dict(
        bloque="Entidad contratante",
        definicion="Departamento donde se ubica la entidad contratante.",
        dominio="32 departamentos + Distrito Capital de Bogotá.",
        rol="Dimensión"),
    "ciudad": dict(
        bloque="Entidad contratante",
        definicion="Municipio donde se ubica la entidad contratante.",
        dominio="Subconjunto de los 1.103 municipios del país.",
        rol="Dimensión"),
    "orden": dict(
        bloque="Entidad contratante",
        definicion="Nivel administrativo de la entidad dentro de la organización del Estado.",
        dominio="Nacional | Territorial | Corporación Autónoma.",
        rol="Dimensión"),
    "sector": dict(
        bloque="Entidad contratante",
        definicion="Sector administrativo al que está adscrita la entidad (Decreto 1082 de 2015).",
        dominio="~25 sectores administrativos del Estado colombiano.",
        rol="Dimensión"),
    "rama": dict(
        bloque="Entidad contratante",
        definicion="Rama del poder público a la que pertenece la entidad.",
        dominio="Ejecutivo | Legislativo | Judicial | Corporación Autónoma.",
        rol="Dimensión"),
    "entidad_centralizada": dict(
        bloque="Entidad contratante",
        definicion="Indica si la entidad hace parte del sector central o del descentralizado.",
        dominio="Centralizada | Descentralizada.",
        rol="Dimensión"),
    "tipo_de_contrato": dict(
        bloque="Objeto y modalidad",
        definicion="Tipología contractual. El dataset viene pre-filtrado a contratos de bienes.",
        dominio="Compraventa | Suministros.",
        rol="Dimensión"),
    "modalidad_de_contratacion": dict(
        bloque="Objeto y modalidad",
        definicion="Procedimiento de selección del contratista (Ley 80/1993 y Ley 1150/2007).",
        dominio="Mínima cuantía, subasta inversa, licitación pública, régimen especial, directa.",
        rol="Dimensión"),
    "codigo_de_categoria_principal": dict(
        bloque="Objeto y modalidad",
        definicion="Clasificador UNSPSC del bien. 'V1.' + 8 dígitos = segmento(2)+familia(2)+clase(2)+producto(2).",
        dominio="Patrón V1.<8 dígitos>.",
        rol="Dimensión"),
    "objeto_del_contrato": dict(
        bloque="Objeto y modalidad",
        definicion="Descripción en texto libre de lo que se contrata.",
        dominio="Texto libre; la fuente lo trunca a 500 caracteres.",
        rol="Texto libre"),
    "fecha_de_firma": dict(
        bloque="Temporalidad",
        definicion="Fecha de suscripción del contrato entre entidad y contratista.",
        dominio="Ventana de extracción del dataset.",
        rol="Métrica temporal"),
    "fecha_de_inicio_del_contrato": dict(
        bloque="Temporalidad",
        definicion="Fecha de inicio de ejecución, usualmente la del acta de inicio.",
        dominio="Debe ser posterior o igual a la fecha de firma.",
        rol="Métrica temporal"),
    "fecha_de_fin_del_contrato": dict(
        bloque="Temporalidad",
        definicion="Fecha de terminación prevista del contrato.",
        dominio="Debe ser posterior a la fecha de inicio.",
        rol="Métrica temporal"),
    "duraci_n_del_contrato": dict(
        bloque="Temporalidad",
        definicion="Plazo pactado, expresado como texto con cantidad y unidad.",
        dominio="'<n> Día(s) | Mes(es) | Año(s) | Semana(s) | Hora(s)'.",
        rol="Derivable"),
    "condiciones_de_entrega": dict(
        bloque="Objeto y modalidad",
        definicion="Condición logística o Incoterm pactado para la entrega de los bienes.",
        dominio="Incoterms (EXW, FOB, CIF, DAP...) o descripciones libres.",
        rol="Dimensión"),
    "proveedor_adjudicado": dict(
        bloque="Proveedor",
        definicion="Razón social o nombre del contratista adjudicatario.",
        dominio="Texto libre; alta cardinalidad.",
        rol="Dimensión"),
    "documento_proveedor": dict(
        bloque="Proveedor",
        definicion="NIT o documento de identidad del contratista.",
        dominio="NIT de 9 dígitos, cédula de 8-10 dígitos, o documento extranjero.",
        rol="Identificador secundario"),
    "es_pyme": dict(
        bloque="Proveedor",
        definicion="Indica si el contratista está registrado como micro, pequeña o mediana empresa.",
        dominio="Si | No.",
        rol="Dimensión"),
    "es_grupo": dict(
        bloque="Proveedor",
        definicion="Indica si el contratista es un proponente plural (consorcio o union temporal).",
        dominio="Si | No.",
        rol="Dimensión"),
    "g_nero_representante_legal": dict(
        bloque="Proveedor",
        definicion="Género declarado del representante legal del contratista.",
        dominio="Hombre | Mujer | Otro.",
        rol="Dimensión"),
    "nacionalidad_representante_legal": dict(
        bloque="Proveedor",
        definicion="País de nacionalidad del representante legal, en código ISO 3166-1 alfa-2.",
        dominio="Códigos de 2 letras.",
        rol="Dimensión"),
    "valor_del_contrato": dict(
        bloque="Financiero",
        definicion="Valor total pactado del contrato, incluidas adiciones.",
        dominio="Pesos colombianos, no negativo.",
        rol="Métrica"),
    "valor_pagado": dict(
        bloque="Financiero",
        definicion="Monto efectivamente desembolsado al contratista a la fecha de corte.",
        dominio="COP, entre 0 y el valor del contrato.",
        rol="Métrica"),
    "valor_facturado": dict(
        bloque="Financiero",
        definicion="Monto facturado por el contratista a la fecha de corte.",
        dominio="COP, entre 0 y el valor del contrato.",
        rol="Métrica"),
    "valor_pendiente_de_pago": dict(
        bloque="Financiero",
        definicion="Saldo pendiente de desembolso a la fecha de corte.",
        dominio="COP, no negativo.",
        rol="Métrica"),
    "dias_adicionados": dict(
        bloque="Temporalidad",
        definicion="Días de prórroga acumulados sobre el plazo original.",
        dominio="Entero no negativo.",
        rol="Métrica"),
    "habilita_pago_adelantado": dict(
        bloque="Financiero",
        definicion="Indica si el contrato contempla anticipo o pago anticipado.",
        dominio="Si | No.",
        rol="Dimensión"),
    "el_contrato_puede_ser_prorrogado": dict(
        bloque="Temporalidad",
        definicion="Indica si el clausulado permite prorrogar el plazo.",
        dominio="Si | No.",
        rol="Dimensión"),
    "origen_de_los_recursos": dict(
        bloque="Financiero",
        definicion="Fuente presupuestal que financia el contrato.",
        dominio="Recursos Propios | Distribuido (Presupuesto General de la Nación).",
        rol="Dimensión"),
    "destino_gasto": dict(
        bloque="Financiero",
        definicion="Clasificación presupuestal del gasto.",
        dominio="Funcionamiento | Inversión.",
        rol="Dimensión"),
    "estado_contrato": dict(
        bloque="Trazabilidad",
        definicion="Estado del contrato dentro de su ciclo de vida en SECOP II.",
        dominio="Borrador, Aprobado, En ejecución, Modificado, Suspendido, Cedido, Terminado, Cerrado, Cancelado.",
        rol="Dimensión"),
    "liquidaci_n": dict(
        bloque="Trazabilidad",
        definicion="Indica si el contrato está sujeto a liquidación (cierre formal bilateral).",
        dominio="Si | No.",
        rol="Dimensión"),
    "obligaci_n_ambiental": dict(
        bloque="Trazabilidad",
        definicion="Indica si el contrato conlleva obligaciones ambientales específicas.",
        dominio="Si | No.",
        rol="Dimensión"),
    "urlproceso": dict(
        bloque="Trazabilidad",
        definicion="Enlace al expediente público del proceso en SECOP II.",
        dominio="Diccionario Python serializado como texto: {'url': 'https://...'}.",
        rol="Enlace"),
}
