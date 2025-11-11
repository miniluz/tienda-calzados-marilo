def zapato_to_dict(zapato):
    return {
        "id": zapato.id,
        "nombre": zapato.nombre,
        "marca": zapato.marca.nombre if zapato.marca else None,
        "precio": int(zapato.precio) if zapato.precio is not None else None,
        "descripcion": zapato.descripcion,
        "estaDisponible": zapato.estaDisponible,
        "estaDestacado": zapato.estaDestacado,
        "fechaCreacion": zapato.fechaCreacion.isoformat() if zapato.fechaCreacion else None,
        "fechaActualizacion": zapato.fechaActualizacion.isoformat() if zapato.fechaActualizacion else None,
        "categoria": zapato.categoria.nombre if zapato.categoria else None,
    }
