def zapato_to_dict(zapato):
    return {
        "id": zapato.id,
        "nombre": zapato.nombre,
        "marca": zapato.marca,
        "talla": float(zapato.talla) if zapato.talla is not None else None,
        "precio": float(zapato.precio) if zapato.precio is not None else None,
        "descripcion": zapato.descripcion,
        "estaDisponible": zapato.estaDisponible,
        "estaDestacado": zapato.estaDestacado,
        "fechaCreacion": zapato.fechaCreacion.isoformat() if zapato.fechaCreacion else None,
        "fechaActualizacion": zapato.fechaActualizacion.isoformat() if zapato.fechaActualizacion else None,
        "categoria": [cat.nombre for cat in zapato.categoria.all()],
        "imagenes": [img.imagen.url for img in zapato.imagenes.all()],
    }
