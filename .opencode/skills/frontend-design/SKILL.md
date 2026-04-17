# Frontend Design Skill

Habilildades y criterios para diseñar interfaces de usuario siguiendo principios de UX/UI profesional.

## Principios de Diseño

### 1. Espaciado y Layout
- Usar `gap` de Tailwind para spacing consistente
- Padding interno mínimo de `p-4` (16px) en tarjetas
- Margenes proporcionales entre secciones

### 2. Tipografía
- Títulos: `text-2xl font-bold text-gray-900` 
- Subtítulos: `text-lg font-semibold text-gray-700`
- Cuerpo: `text-base text-gray-600`
- Labels: `text-sm text-gray-500`

### 3. Colores y Estados
- Fondo página: `bg-white` o `bg-gray-50`
- Tarjetas: `bg-white border border-gray-200 rounded-xl shadow-sm`
- Estados activos: `text-primary-600`
- Estados hover: `hover:bg-gray-50`

### 4. Componentes
- Botones primarios: `bg-primary-500 text-white rounded-lg px-4 py-2`
- Botones secundarios: `bg-white border border-gray-200 text-gray-700`
- Inputs: `border border-gray-300 rounded-lg px-3 py-2 focus:ring-2`

### 5. Responsive
- Mobile: `grid-cols-2` para listas de estadísticas
- Desktop: `grid-cols-4` o contenido centrado con `max-w-7xl`

### 6. Navegación
- Navbar fija con `z-50` mínimo
- Padding bottom en main para evitar contenido oculto: `pb-24` o mayor
- No usar `overflow-hidden` a menos que sea necesario

## Reglas Anti-Error

- ❌ NO usar `overflow-x-hidden` en el body
- ❌ NO usar `min-height: 100vh` sin `overflow-auto`
- ❌ NO mezclar `text-gray-*` con `text-slate-*`
- ❌ NO usar gradientes complejos a menos que sea necesario

## Checklist de Verificación

Antes de commit siempre verificar:
- [ ] Scroll funciona en móvil
- [ ] Texto no se desborda de las tarjetas
- [ ] Colores consistentes (gray o slate, no ambos)
- [ ] Padding adecuado en todos los componentes