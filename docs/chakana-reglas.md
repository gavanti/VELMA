# Reglas de Negocio - Chakana Platform

## Aurios - Unidad de Valor

El **Aurio** es la unidad de valor de la plataforma Chakana.

### Constraint: Valor del Aurio

**El Aurio vale exactamente $0.01 USD. No aplicar márgenes ni conversiones.**

Esta regla es absoluta y nunca debe modificarse.

## Embajadores

Los Embajadores son usuarios que acumulan Aurios por completar Misiones.

### Regla de Acumulación

Los Embajadores acumulan Aurios por cada Misión completada exitosamente.

- Misión básica: 100 Aurios
- Misión premium: 500 Aurios
- Misión especial: 1000 Aurios

### Procedimiento: Canje de Aurios

Para que un Embajador canjee sus Aurios:

1. Verificar saldo mínimo de 1000 Aurios
2. Solicitar canje mediante el endpoint `/api/v1/canjes`
3. Validar identidad del Embajador
4. Procesar transferencia en máximo 48 horas

## Tambus

Un **Tambu** es un comercio aliado en la plataforma Chakana.

### Concepto

Los Tambus ofrecen beneficios exclusivos a los Embajadores y recuyen visibilidad a través de la plataforma.

### Registro de Tambu

Para registrar un nuevo Tambu:

1. Completar formulario de solicitud
2. Validar documentación comercial
3. Aprobar por equipo de operaciones
4. Activar en plataforma

## Ejemplo: Flujo Completo

Ejemplo de cómo un Embajador completa una Misión y acumula Aurios:

1. Embajador Juan recibe notificación de Misión
2. Completa la Misión "Visita restaurante X"
3. Sube evidencia (foto del recibo)
4. Sistema valida la evidencia
5. Juan recibe 100 Aurios en su cuenta
6. Juan puede ver su saldo actualizado en tiempo real
