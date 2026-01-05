Memoria Compartida (State)Todos los agentes leen y escriben en este objeto JSON vivo:JSON{
  "intencion": null,         // SOLICITAR_TAXI, CARGA, etc.
  "direccion_parseada": null, // Objeto JSON complejo (vía, número, placa)
  "zona_validada": null,     // BARRANQUILLA, SOLEDAD...
  "detalles_vehiculo": [],   // [baúl grande, aire]
  "metodo_pago": "EFECTIVO", // NEQUI, DAVIPLATA...
  "observacion_final": null, // Frase para el conductor
  "agente_actual": "RECEPCIONISTA"
}
1. Agente "El Recepcionista" (Clasificador)Es la primera línea de defensa. Su trabajo es entender qué quiere el usuario y filtrar el ruido.Objetivo: Determinar la intención macro y extraer datos iniciales obvios.Lógica Base (Prompt): Usa las reglas de INTENTION_CLASSIFICATION_PROMPT.Tareas:Clasificar entre SOLICITAR_TAXI, CANCELAR, QUEJA, etc..Priorizar: Si el usuario dice "Taxi para llevar un trasteo", clasifica como SOLICITAR_TAXI_CARGA.Normalizar audios iniciales (ej: "nequi" en lugar de "nek").Transición (Handoff):Si la intención es solicitar servicio $\rightarrow$ Pasa a Agente Navegante.Si es consulta/cancelación $\rightarrow$ Resuelve y cierra.2. Agente "El Navegante" (Especialista en Ubicación)Es el agente más complejo y riguroso. Se encarga exclusivamente de la dirección geográfica.Objetivo: Obtener una dirección estructurada, validada y dentro de la zona de cobertura.Lógica Base (Prompt): Combina ADDRESS_INTERPRETATION_PROMPT y ZONE_VALIDATION_PROMPT.Tareas:Parseo Estricto: Convierte audio a estructura. Aplica la regla crítica de sufijos: "B uno" es B1, pero "B doce" es Letra: B, Num: 12.Auditoría (Self-Correction): Ejecuta la lógica del ADDRESS_VALIDATION_PROMPT para asegurar que no faltan números ni se inventan datos.Validación de Zona: Verifica si es Barranquilla, Soledad, Puerto Colombia o Galapa. Si es "Cartagena", rechaza el servicio amablemente.Transición (Handoff):Si direccion_formateada existe Y zona_valida es true $\rightarrow$ Pasa a Agente Operador.Si la dirección es ambigua $\rightarrow$ Pregunta al usuario (Bucle interno).3. Agente "El Operador" (Detalles y Logística)Se encarga de los "adornos" del servicio: pago y tipo de carro.Objetivo: Refinar el pedido con necesidades específicas y generar la nota para el conductor.Lógica Base (Prompt): Usa SERVICE_DETAILS_PROCESSING_PROMPT.Tareas:Extracción de Pago: Detecta y normaliza "nequi", "daviplata", "datafono".Características: Identifica "baúl grande", "aire acondicionado", "mascota".Redacción Operativa: Genera la OBSERVACION.Input: "Voy para el aeropuerto con unas maletas grandes".Output: "Pasajero en aeropuerto, lleva equipaje" (Tercera persona, sin saludos).Transición (Handoff):Una vez tiene la observación generada y el pago definido $\rightarrow$ Pasa a Agente Confirmador.4. Agente "El Confirmador" (Cierre)El encargado de dar seguridad al usuario y enviar la data al backend.Objetivo: Presentar el resumen final y obtener el "Sí".Lógica Base: No requiere un prompt complejo de extracción, sino de formato.Tareas:Reconstruir la frase de confirmación: "Confirmo: Taxi en [Dirección Formateada] en [Zona]. Pago con [Método]. [Observación]. ¿Es correcto?".Manejar cambios de último minuto (ej: "Ay, cambia el pago a efectivo"). Si esto pasa, devuelve el control al Agente Operador.Transición Final:Usuario dice "Sí" $\rightarrow$ Trigger API Backend (Dispatch).Diagrama de Transición de EstadoFragmento de códigograph TD
    User[Mensaje del Usuario] --> A[Agente Recepcionista]
    
    A -- "Intención: Taxi" --> B[Agente Navegante]
    A -- "Otra intención" --> X[Responder y Cerrar]
    
    B -- "¿Dirección confusa?" --> B
    B -- "Dirección OK + Zona OK" --> C[Agente Operador]
    
    C -- "Faltan detalles?" --> C
    C -- "Datos Completos" --> D[Agente Confirmador]
    
    D -- "Usuario corrige dirección" --> B
    D -- "Usuario corrige pago" --> C
    D -- "Usuario Confirma" --> E[FIN: Enviar a API]
¿Por qué esta estructura es mejor?Aislamiento de Errores: Si el sistema falla en entender la dirección, el error se queda aislado en el Agente Navegante, sin afectar la lógica de pagos.Especialización del Prompt: El Agente Navegante puede tener un prompt con muchos ejemplos de direcciones ("carrera 43 b uno"), mientras que el Agente Operador tiene un prompt enfocado solo en pagos y vehículos, evitando que el contexto se diluya.Manejo de "State": Permite que el usuario diga "ah, y voy con perro" en cualquier momento, y el sistema sabe que ese dato pertenece al Agente Operador, aunque esté hablando con el Confirmador.