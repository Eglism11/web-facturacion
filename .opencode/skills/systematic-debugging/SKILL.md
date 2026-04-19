---
name: systematic-debugging
description: Debug and fix issues in web-facturacion project
---

## Instructions for AI

1. Mantener siempre el puerto dinámico con `os.environ.get('PORT')`.
2. Verificar que el builder en `railway.json` sea 'nixpacks' en minúsculas.
3. Siempre verificar la configuración de Supabase en las variables de entorno.