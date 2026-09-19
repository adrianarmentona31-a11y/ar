import { api } from "./api";

export async function createSurveyLink(serviceId) {
  const { data } = await api.post("/surveys", { service_id: serviceId });
  const url = `${window.location.origin}/encuesta/${data.token}`;
  return { ...data, url };
}

export function whatsappSurveyUrl(survey, url) {
  const name = (survey.client_name || "").split(" ")[0];
  const text = `Hola${name ? ` ${name}` : ""}, gracias por confiar en Armenta's Motors Company. ¿Nos ayudas con 1 minuto para calificar tu servicio ${survey.folio}? ${url}`;
  const phone = (survey.client_phone || "").replace(/\D/g, "");
  return `https://wa.me/${phone}?text=${encodeURIComponent(text)}`;
}
