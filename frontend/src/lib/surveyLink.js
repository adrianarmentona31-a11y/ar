export function whatsappSurveyUrl({ clientName, clientPhone, folio, surveyUrl }) {
  const name = (clientName || "").split(" ")[0];
  const text = `Hola${name ? ` ${name}` : ""}, gracias por confiar en Armenta's Motors Company. ¿Nos ayudas con 1 minuto para calificar tu servicio${folio ? ` ${folio}` : ""}? ${surveyUrl}`;
  const phone = (clientPhone || "").replace(/\D/g, "");
  return `https://wa.me/${phone}?text=${encodeURIComponent(text)}`;
}
