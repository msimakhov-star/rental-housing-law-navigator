'use strict';
/* Rental Housing Law Navigator: static UI. It reads data/lookups_detail.json and does no legal logic. */

const $ = (s, r = document) => r.querySelector(s);
function h(tag, attrs, ...kids) {
  const e = document.createElement(tag);
  for (const k in attrs || {}) {
    const v = attrs[k];
    if (v == null || v === false) continue;
    if (k === 'class') e.className = v;
    else if (k.startsWith('on')) e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v === true ? '' : v);
  }
  for (const c of kids.flat()) {
    if (c == null || c === false) continue;
    e.append(c.nodeType ? c : document.createTextNode(String(c)));
  }
  return e;
}

const DEFAULT_ASOF = '2026-10-01';
const QUICK = ['2025-12-31', '2026-01-02', '2026-10-01', '2027-07-02'];
const QUICK_NOTE = {
  en: { '2025-12-31': 'day before CA AB 325', '2026-01-02': 'AB 325 in force', '2026-10-01': 'default as-of date', '2027-07-02': 'NJ FAIR Act in force' },
  es: { '2025-12-31': 'día antes de CA AB 325', '2026-01-02': 'AB 325 en vigor', '2026-10-01': 'fecha por defecto', '2027-07-02': 'NJ FAIR Act en vigor' },
};
const STATUS_NAME = { en: { in_force: 'In force', not_yet_effective: 'Not yet effective', pending: 'Pending bill', failed: 'Failed (not law)' }, es: { in_force: 'Vigente', not_yet_effective: 'Aún no vigente', pending: 'Proyecto pendiente', failed: 'Fallido (no es ley)' } };
const FACT_NAME = { en: { year_built: 'year built', units: 'units', units_min: 'units (minimum)', building_age_years: 'building age', co_date: 'certificate of occupancy date' }, es: { year_built: 'año de construcción', units: 'unidades', units_min: 'unidades (mínimo)', building_age_years: 'antigüedad del edificio', co_date: 'fecha del certificado de ocupación' } };
const TEST_SUMMARY = {
  en: {
    T1: 'California\'s ban on shared pricing software for rents is not yet in effect on the first date and applies on the second, for every California address in the sample.',
    T2: 'Hoboken and Jersey City each have their own local ban on algorithmic rent-setting. Each applies only to addresses in its own city, and Newark addresses get neither.',
    T3: 'New Jersey\'s FAIR Act is enacted but starts later: it is not yet in effect on the first date and applies on the second, for every New Jersey address. Hoboken and Jersey City addresses are flagged for human review because their local bans may conflict with it.',
    T4: 'Two Massachusetts bills on algorithmic rent-setting are only proposals, not law. Every Boston and Cambridge address therefore lists both as Pending. That is why the count shows 220 pending entries for 110 addresses: two bills per address.',
    T5: 'A Massachusetts ballot question that would have allowed rent control did not pass. So no rent cap is reported for Boston or Cambridge, and no address is affected.',
  },
  es: {
    T1: 'La prohibición de California sobre el software de precios compartidos para alquileres aún no está vigente en la primera fecha y se aplica en la segunda, para todas las direcciones de California de la muestra.',
    T2: 'Hoboken y Jersey City tienen cada una su propia prohibición local de la fijación algorítmica de alquileres. Cada una se aplica solo a las direcciones de su ciudad, y las direcciones de Newark no tienen ninguna.',
    T3: 'La FAIR Act de Nueva Jersey está aprobada pero empieza más tarde: aún no está vigente en la primera fecha y se aplica en la segunda, para todas las direcciones de Nueva Jersey. Las direcciones de Hoboken y Jersey City se marcan para revisión humana porque sus prohibiciones locales podrían entrar en conflicto con ella.',
    T4: 'Dos proyectos de ley de Massachusetts sobre la fijación algorítmica de alquileres son solo propuestas, no ley. Por eso cada dirección de Boston y Cambridge los muestra a ambos como Pendientes. Así se explica que el recuento muestre 220 entradas pendientes para 110 direcciones: dos proyectos por dirección.',
    T5: 'Una iniciativa electoral de Massachusetts que habría permitido el control de alquileres no fue aprobada. Por eso no se informa ningún límite de alquiler para Boston ni Cambridge, y ninguna dirección resulta afectada.',
  },
};
const EXAMPLES = ['A0016', 'A0001', 'A0002', 'A0009', 'A0005'];
const CATS = ['rent_increase_limits', 'just_cause_eviction', 'security_deposits', 'application_screening_fees', 'screening_restrictions', 'algorithmic_rent_setting'];
const STATUSES = ['applies', 'unknown', 'superseded', 'not_yet_effective', 'pending'];
const ICONS = {
  applies: '<path d="M3 8.5l3 3 7-7"/>',
  unknown: '<path d="M6 6.2a2 2 0 114 0c0 1.5-2 1.6-2 3.2M8 12.2v.6"/>',
  superseded: '<path d="M2.5 5h10m-3-3l3 3-3 3M13.5 11h-10m3-3l-3 3 3 3"/>',
  not_yet_effective: '<circle cx="8" cy="8" r="6"/><path d="M8 4.5V8l2.5 1.5"/>',
  flag: '<path d="M4 14V2m0 1h8l-2 3 2 3H4"/>',
  pending: '<circle cx="8" cy="8" r="6" stroke-dasharray="2.2 2.2"/>',
};
function icon(name) {
  const s = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  s.setAttribute('viewBox', '0 0 16 16'); s.setAttribute('fill', 'none'); s.setAttribute('stroke', 'currentColor');
  s.setAttribute('stroke-width', '2'); s.setAttribute('stroke-linecap', 'round'); s.setAttribute('stroke-linejoin', 'round');
  s.setAttribute('aria-hidden', 'true'); s.innerHTML = ICONS[name] || ''; // static strings only
  return s;
}

/* ---------- strings ---------- */
const I18N = {
  en: {
    skip: 'Skip to content', title: 'Rental Housing Law Navigator',
    banner_strong: 'Not legal advice.', banner_rest: 'Plain-language summaries of public law, built for a hackathon prototype.',
    tab_lookup: 'Address lookup', tab_changes: 'What changed', tab_how: 'How it works and audit',
    loading: 'Loading the rules data (about 7 MB, once)...', loading_mb: (a, b) => `Loading the rules data: ${a} MB${b ? ' of ' + b + ' MB' : ''}...`,
    load_fail: 'Could not load the data file. If you opened this page from disk, serve the folder over http instead (for example: python3 -m http.server). Details: ',
    h_lookup: 'Find an address', lookup_intro: 'Search the 500 sample addresses by street, address id or city. Results show which rules our sources say may apply, and what we could not tell.',
    search_label: 'Address, id (for example A0016) or city', asof_label: 'As-of date', no_match: 'No address matches that text.',
    pick_hint: 'Pick an address above to see which rules our sources say may apply on the chosen date.',
    live_update: (n, d, a) => `${n} rules shown for ${a} as of ${d}.`,
    addr_facts: 'Building facts', addr_stack: 'Where it sits (State, County, City)', id: 'Address id',
    year_built: 'Year built', units: 'Units', use: 'Use',
    year_missing: 'Not in the public records we used. Rules that depend on building age stay "Unknown" for this address.',
    units_exact: n => `${n} (exact count from the assessor)`,
    units_min: n => `At least ${n}. The exact count is not in our data, so rules with a unit threshold may stay "Unknown".`,
    units_none: 'Not available. Rules with a unit threshold stay "Unknown".', use_none: 'Not available',
    state: 'State', county: 'County', city: 'City', county_none: 'not identified', city_none: 'none of the 10 covered cities, so only state-level rules were checked',
    matched: 'Matched address', geocode: 'Location match',
    geo_exact: 'Exact match.', geo_non_exact: 'Approximate match. The city assignment is less certain.', geo_fallback_postal: 'Address not found by the geocoder. City taken from the postal city, so confidence is reduced.', geo_failed: 'Location could not be matched.',
    dl_json: 'Download report (JSON)', dl_print: 'Print or save as PDF',
    shown: (n, d) => `${n} rules shown as of ${d}`,
    asof_on: d => `As of ${d}`, key_fig: 'Key figure', conf: 'Confidence', conf_hi: 'high', conf_mid: 'medium', conf_lo: 'low',
    conf_note: 'How sure the extraction step was about this rule. Not a probability that the answer is legally correct.',
    why_missing: 'Why we are not sure: we do not have these facts', facts_used: 'Facts used',
    reason: 'For this address:', lowconf: 'Low confidence: flagged for human review', likely: (lab, use, min) => `Likely: ${lab}, if the property class${use ? ' (' + use + ')' : ''} means at least ${min} units. This is a hint, not part of the official answer.`, likely_not: 'does not apply', no_rule_plain: 'We found no rule at this level in our sources.', gap_plain: 'We could not check this level: no source text was available.', reviewers: 'Details for reviewers', flag_title: 'Flagged for human review.', source: 'Source', citation: 'Citation', quote: 'Quoted text from the source', link: 'Source link', retrieved: 'Retrieved',
    doc_id: 'Document id', origin: 'Origin', origin_D: 'Supplied corpus document', origin_X: 'Supplemental public page (not part of the supplied corpus)',
    rule_status: 'Rule status in our records', eff: 'Effective date', no_eff: 'not stated',
    src_caveat: 'Sources are public pages as of the retrieval date and may have changed since. Check the official text before relying on it.',
    juris: 'Jurisdiction', lvl_state: 'State', lvl_county: 'County', lvl_city: 'City', lvl_local: 'Local',
    no_rule_h: 'No rule found at this level in our sources.', no_rule_sub: 'That is what we found, not proof that no rule exists.',
    gap_h: 'We could not check this:', nothing_h: 'No rule found in our sources for this category on this date.', nothing_sub: 'That does not prove that none exists.',
    also: n => `What else we checked (${n})`, title_en_note: 'Rule titles and notes are in English as published.',
    h_changes: 'What changed', changes_intro: 'Five tests show how answers move with dates and with bills that are enacted, pending or failed. Click an address to open it at the right date.',
    t_expected: 'Expected behaviour', t_before: 'Before', t_after: 'After', t_date: 'Date', t_counts: 'Result counts', t_city: 'Affected addresses by city', t_affected: n => `Affected addresses (${n})`,
    t_conflict: n => `Addresses flagged for human review (${n})`, t_rules: 'Rules tested', t_notes: 'How this was computed', t_empty: 'No address is affected. That is the expected result for this test.',
    t_opens: d => `Each address opens as of ${d}.`, show_all: n => `Show all ${n}`, type_as_of: 'Date change', type_boundary: 'Boundary check', type_pending: 'Pending bills', type_negative: 'Negative check',
    h_how: 'How it works and audit', how_intro: 'Every answer is built by a fixed pipeline from public legal text. This page shows the stages, the sources, what was checked and what we cannot promise.',
    h_extract: 'How the rules were extracted', extract: ['Rule extraction was run by Claude models (Sonnet and Opus tiers), driven by Claude Code agents following the prompt files in the repository.', 'Deterministic validators then check every record, and every quoted span is verified verbatim against the source text.', 'Three independent review passes followed.', 'The stages are cached and can be replayed offline.', 'The repository also contains a pluggable runner for local and API models. A small local open-model demo exists, with lower quality.', 'There is no official scorer. Our evaluation is a self-made proxy.', 'The answer key and the number of teams are unknown.'], h_pipe: 'The five stages', h_sources: 'Sources', h_valid: 'Validation summary', h_guard: 'Responsible-design guardrails', h_limits: 'Limitations, stated plainly', h_scale: 'Scalability path', h_runs: 'Audit log of pipeline runs',
    pipe: [['Extract', 'An AI model reads each legal document and fills a structured rule record. Every record must carry a citation and a verbatim quote that is checked against the source text.', 'work/extract'],
      ['Resolve', 'Each address is matched to its State, County and City with a geocoder, with a confidence note.', 'work/jurisdictions'],
      ['Apply', 'Fixed code (no AI) tests each rule against known building facts: applies, does not apply, or unknown when a fact is missing.', 'navigator/apply'],
      ['Explain', 'Each result gets a plain-language explanation in English and Spanish, the key figure and the source.', 'lookups_detail.json'],
      ['Track change', 'The same rules are re-run for other dates and for pending bills, to list which addresses change.', 'changes.json']],
    src_cols: ['Document id', 'Origin', 'Source URL', 'Retrieved'], src_count: (n, d, x) => `${n} documents: ${d} from the supplied corpus, ${x} supplemental public pages.`,
    valid_rules: 'Rule records pass validation', valid_quotes: 'Quoted spans found verbatim in the source text', gen: 'Data generated', n_addr: 'Addresses', n_rules: 'Rules in the data', n_runs: 'Logged pipeline runs',
    guard: ['Cite everything: each rule shows its citation, a verbatim quote, a link and a retrieval date.', 'Say "unknown": when a needed fact is missing we say so and name the fact, instead of guessing.', 'Separate enacted from pending: in force, not yet effective, superseded and pending bills have different labels.', 'Conflict flags: possible preemption between levels of law is flagged for human review.', 'Audit log: model calls, decisions and validation runs are recorded.', 'No advice on avoiding rules: this tool describes what public sources say. It does not tell anyone how to get around a rule, and it is not a compliance check.'],
    limits: ['Only exact assessor unit counts are used. Many New Jersey and Berkeley answers are Unknown because the data gives only a class such as "5 or more units".', 'We model the current version of each rule. Earlier versions may have applied on earlier dates.', 'Some rules rest on supplemental public pages that are not part of the supplied corpus.', 'A unit-class hint exists (for example, a property class that means at least 5 units) and is shown as "Likely", but it is not used for the official answers.', 'Facts we do not have, such as owner occupancy, tenancy length, rent level or subsidies, always leave exemptions Unknown.', 'No lawyer has reviewed these summaries. Spanish text is provided for convenience: the English text and the quoted source are the reference.', 'Public pages change. The retrieval date shows how old each source is.'],
    scale: ['Add documents: drop new legal text into the corpus folder.', 'Rerun the stages: extract, resolve, apply, explain, track change. Validation and the audit log run each time.', 'New jurisdictions need their source text, one configuration entry and a parcel-data adapter; the rules engine and this interface do not change.', 'Better inputs improve answers: more building facts turn Unknown results into firm ones.'],
    foot: g => `Data generated ${g}. Not legal advice. This prototype describes public sources and does not certify compliance.`,
    download_name: 'report',
    glance: 'At a glance', try_ex: 'Try an example:', glance_none: 'No rule found', glance_gap: 'Not checked', n_rules_short: n => `${n} rules`, flag_short: 'Review',
    changed: (d, w) => `Changed since ${d}: was ${w}`, was_none: 'not listed', n_changed: (n, d) => `${n} changed since ${d}`,
    status_key: 'Status key', cats_h: 'Six categories we check',
  },
  es: {
    skip: 'Saltar al contenido', title: 'Navegador de la ley de vivienda en alquiler',
    banner_strong: 'No es asesoramiento legal.', banner_rest: 'Resúmenes en lenguaje sencillo de leyes públicas, creados como prototipo de hackathon.',
    tab_lookup: 'Buscar dirección', tab_changes: 'Qué cambió', tab_how: 'Cómo funciona y auditoría',
    loading: 'Cargando los datos de las normas (unos 7 MB, una sola vez)...', loading_mb: (a, b) => `Cargando los datos: ${a} MB${b ? ' de ' + b + ' MB' : ''}...`,
    load_fail: 'No se pudo cargar el archivo de datos. Si abrió la página desde el disco, sírvala por http (por ejemplo: python3 -m http.server). Detalles: ',
    h_lookup: 'Buscar una dirección', lookup_intro: 'Busque entre las 500 direcciones de muestra por calle, id o ciudad. Los resultados muestran qué normas pueden aplicar según nuestras fuentes y qué no pudimos determinar.',
    search_label: 'Dirección, id (por ejemplo A0016) o ciudad', asof_label: 'Fecha de consulta', no_match: 'Ninguna dirección coincide con ese texto.',
    pick_hint: 'Elija una dirección arriba para ver qué normas pueden aplicar, según nuestras fuentes, en la fecha elegida.',
    live_update: (n, d, a) => `${n} normas mostradas para ${a} a fecha de ${d}.`,
    addr_facts: 'Datos del edificio', addr_stack: 'Dónde se ubica (Estado, Condado, Ciudad)', id: 'Id de dirección',
    year_built: 'Año de construcción', units: 'Unidades', use: 'Uso',
    year_missing: 'No figura en los registros públicos que usamos. Las normas que dependen de la antigüedad del edificio quedan como "Desconocido" para esta dirección.',
    units_exact: n => `${n} (recuento exacto del tasador)`,
    units_min: n => `Al menos ${n}. El recuento exacto no está en nuestros datos, así que las normas con umbral de unidades pueden quedar como "Desconocido".`,
    units_none: 'No disponible. Las normas con umbral de unidades quedan como "Desconocido".', use_none: 'No disponible',
    state: 'Estado', county: 'Condado', city: 'Ciudad', county_none: 'no identificado', city_none: 'ninguna de las 10 ciudades cubiertas, por lo que solo se revisaron normas estatales',
    matched: 'Dirección encontrada', geocode: 'Coincidencia de ubicación',
    geo_exact: 'Coincidencia exacta.', geo_non_exact: 'Coincidencia aproximada. La asignación de ciudad es menos segura.', geo_fallback_postal: 'El geocodificador no encontró la dirección. La ciudad se tomó de la ciudad postal, por lo que la confianza es menor.', geo_failed: 'No se pudo ubicar la dirección.',
    dl_json: 'Descargar informe (JSON)', dl_print: 'Imprimir o guardar como PDF',
    shown: (n, d) => `${n} normas mostradas a fecha de ${d}`,
    asof_on: d => `A fecha de ${d}`, key_fig: 'Cifra clave', conf: 'Confianza', conf_hi: 'alta', conf_mid: 'media', conf_lo: 'baja',
    conf_note: 'Qué tan segura estaba la extracción sobre esta norma. No es la probabilidad de que la respuesta sea legalmente correcta.',
    why_missing: 'Por qué no estamos seguros: nos faltan estos datos', facts_used: 'Datos usados',
    reason: 'Para esta dirección:', lowconf: 'Confianza baja: marcado para revisión humana', likely: (lab, use, min) => `Probable: ${lab}, si la clase de propiedad${use ? ' (' + use + ')' : ''} significa al menos ${min} unidades. Es una pista, no forma parte de la respuesta oficial.`, likely_not: 'no aplica', no_rule_plain: 'No encontramos ninguna norma en este nivel en nuestras fuentes.', gap_plain: 'No pudimos comprobar este nivel: no había texto de la fuente disponible.', reviewers: 'Detalles para revisores', flag_title: 'Marcado para revisión humana.', source: 'Fuente', citation: 'Cita', quote: 'Texto citado de la fuente', link: 'Enlace a la fuente', retrieved: 'Consultado',
    doc_id: 'Id del documento', origin: 'Origen', origin_D: 'Documento del corpus suministrado', origin_X: 'Página pública complementaria (no forma parte del corpus suministrado)',
    rule_status: 'Estado de la norma en nuestros registros', eff: 'Fecha de entrada en vigor', no_eff: 'no indicada',
    src_caveat: 'Las fuentes son páginas públicas a la fecha de consulta y pueden haber cambiado. Verifique el texto oficial antes de confiar en él.',
    juris: 'Jurisdicción', lvl_state: 'Estado', lvl_county: 'Condado', lvl_city: 'Ciudad', lvl_local: 'Local',
    no_rule_h: 'No encontramos ninguna norma en este nivel en nuestras fuentes.', no_rule_sub: 'Eso es lo que encontramos, no prueba de que no exista una norma.',
    gap_h: 'No pudimos comprobar esto:', nothing_h: 'No encontramos ninguna norma en nuestras fuentes para esta categoría en esta fecha.', nothing_sub: 'Eso no prueba que no exista.',
    also: n => `Qué más revisamos (${n})`, title_en_note: 'Los títulos de las normas y las notas están en inglés, como se publicaron.',
    h_changes: 'Qué cambió', changes_intro: 'Cinco pruebas muestran cómo cambian las respuestas con las fechas y con proyectos de ley aprobados, pendientes o fallidos. Pulse una dirección para abrirla en la fecha correcta.',
    t_expected: 'Comportamiento esperado', t_before: 'Antes', t_after: 'Después', t_date: 'Fecha', t_counts: 'Recuento de resultados', t_city: 'Direcciones afectadas por ciudad', t_affected: n => `Direcciones afectadas (${n})`,
    t_conflict: n => `Direcciones marcadas para revisión humana (${n})`, t_rules: 'Normas probadas', t_notes: 'Cómo se calculó', t_empty: 'Ninguna dirección resulta afectada. Es el resultado esperado de esta prueba.',
    t_opens: d => `Cada dirección se abre a fecha de ${d}.`, show_all: n => `Mostrar las ${n}`, type_as_of: 'Cambio de fecha', type_boundary: 'Prueba de límites', type_pending: 'Proyectos pendientes', type_negative: 'Prueba negativa',
    h_how: 'Cómo funciona y auditoría', how_intro: 'Cada respuesta sale de un proceso fijo a partir de texto legal público. Esta página muestra las etapas, las fuentes, lo que se comprobó y lo que no podemos prometer.',
    h_extract: 'Cómo se extrajeron las normas', extract: ['La extracción de normas la ejecutaron modelos Claude (niveles Sonnet y Opus), dirigidos por agentes de Claude Code que siguen los archivos de instrucciones del repositorio.', 'Después, validadores deterministas revisan cada registro, y cada texto citado se verifica literalmente contra el texto de la fuente.', 'Siguieron tres revisiones independientes.', 'Las etapas se guardan en caché y se pueden repetir sin conexión.', 'El repositorio también incluye un ejecutor intercambiable para modelos locales y de API. Existe una pequeña demostración con un modelo abierto local, de menor calidad.', 'No hay un evaluador oficial. Nuestra evaluación es un sustituto hecho por nosotros.', 'Se desconocen la clave de respuestas y el número de equipos.'], h_pipe: 'Las cinco etapas', h_sources: 'Fuentes', h_valid: 'Resumen de validación', h_guard: 'Salvaguardas de diseño responsable', h_limits: 'Limitaciones, dichas con claridad', h_scale: 'Camino de escalabilidad', h_runs: 'Registro de auditoría de las ejecuciones',
    pipe: [['Extraer', 'Un modelo de IA lee cada documento legal y completa un registro estructurado de la norma. Cada registro debe llevar una cita y un texto literal que se comprueba contra la fuente.', 'work/extract'],
      ['Resolver', 'Cada dirección se asigna a su Estado, Condado y Ciudad con un geocodificador, con una nota de confianza.', 'work/jurisdictions'],
      ['Aplicar', 'Código fijo (sin IA) prueba cada norma con los datos conocidos del edificio: aplica, no aplica, o desconocido si falta un dato.', 'navigator/apply'],
      ['Explicar', 'Cada resultado recibe una explicación en lenguaje sencillo en inglés y español, la cifra clave y la fuente.', 'lookups_detail.json'],
      ['Seguir cambios', 'Las mismas normas se vuelven a ejecutar para otras fechas y para proyectos pendientes, y se listan las direcciones que cambian.', 'changes.json']],
    src_cols: ['Id del documento', 'Origen', 'URL de la fuente', 'Consultado'], src_count: (n, d, x) => `${n} documentos: ${d} del corpus suministrado, ${x} páginas públicas complementarias.`,
    valid_rules: 'Los registros de normas pasan la validación', valid_quotes: 'Textos citados encontrados literalmente en la fuente', gen: 'Datos generados', n_addr: 'Direcciones', n_rules: 'Normas en los datos', n_runs: 'Ejecuciones registradas',
    guard: ['Citar todo: cada norma muestra su cita, un texto literal, un enlace y la fecha de consulta.', 'Decir "desconocido": cuando falta un dato necesario lo decimos y lo nombramos, en lugar de adivinar.', 'Separar lo vigente de lo pendiente: vigente, aún no vigente, reemplazada y proyectos pendientes tienen etiquetas distintas.', 'Marcas de conflicto: la posible prevalencia entre niveles de ley se marca para revisión humana.', 'Registro de auditoría: se registran las llamadas al modelo, las decisiones y las validaciones.', 'Sin consejos para evitar normas: esta herramienta describe lo que dicen las fuentes públicas. No dice cómo eludir una norma ni es una verificación de cumplimiento.'],
    limits: ['Solo se usan recuentos exactos de unidades del tasador. Muchas respuestas de Nueva Jersey y Berkeley son Desconocido porque los datos solo dan una clase como "5 o más unidades".', 'Modelamos la versión actual de cada norma. Pueden haber regido versiones anteriores en fechas anteriores.', 'Algunas normas se apoyan en páginas públicas complementarias que no forman parte del corpus suministrado.', 'Existe una pista basada en la clase de propiedad (por ejemplo, una clase que significa al menos 5 unidades) y se muestra como "Probable", pero no se usa para las respuestas oficiales.', 'Los datos que no tenemos, como ocupación por el propietario, duración del arrendamiento, nivel de renta o subsidios, dejan las exenciones como Desconocido.', 'Ningún abogado ha revisado estos resúmenes. El texto en español se ofrece como ayuda: el texto en inglés y la fuente citada son la referencia.', 'Las páginas públicas cambian. La fecha de consulta indica la antigüedad de cada fuente.'],
    scale: ['Añadir documentos: colocar texto legal nuevo en la carpeta del corpus.', 'Volver a ejecutar las etapas: extraer, resolver, aplicar, explicar, seguir cambios. La validación y el registro de auditoría se ejecutan cada vez.', 'Las nuevas jurisdicciones necesitan su texto fuente, una entrada de configuración y un adaptador de datos de parcelas; el motor de normas y esta interfaz no cambian.', 'Mejores datos mejoran las respuestas: más datos del edificio convierten resultados Desconocido en firmes.'],
    foot: g => `Datos generados ${g}. No es asesoramiento legal. Este prototipo describe fuentes públicas y no certifica el cumplimiento.`,
    download_name: 'informe',
    glance: 'De un vistazo', try_ex: 'Pruebe un ejemplo:', glance_none: 'Sin norma encontrada', glance_gap: 'Sin comprobar', n_rules_short: n => `${n} normas`, flag_short: 'Revisar',
    changed: (d, w) => `Cambió desde ${d}: antes ${w}`, was_none: 'no listada', n_changed: (n, d) => `${n} cambiaron desde ${d}`,
    status_key: 'Clave de estados', cats_h: 'Seis categorías que revisamos',
  },
};
const LABELS = {
  en: {
    cat: {
      rent_increase_limits: ['Rent increase limits', 'Caps on how much and how often rent can go up.'],
      just_cause_eviction: ['Just-cause eviction', 'Limits on when a landlord can end a tenancy.'],
      security_deposits: ['Security deposits', 'Caps, handling and return of deposits.'],
      application_screening_fees: ['Application and screening fees', 'What a landlord may charge to apply or be screened.'],
      screening_restrictions: ['Screening restrictions', 'Limits on what can be considered when choosing tenants.'],
      algorithmic_rent_setting: ['Algorithmic rent-setting', 'Rules on software that recommends or sets rents.'],
    },
    st: { applies: 'Applies', unknown: 'Unknown', superseded: 'Superseded', not_yet_effective: 'Not yet effective', pending: 'Pending' },
    stHelp: { applies: 'Our sources say this rule covers this address on this date.', unknown: 'We cannot tell: a fact we need is missing.', superseded: 'A rule at another level takes precedence here.', not_yet_effective: 'Enacted, but not in force on this date.', pending: 'A bill that is not law.' },
  },
  es: {
    cat: {
      rent_increase_limits: ['Límites a los aumentos de alquiler', 'Topes a cuánto y con qué frecuencia puede subir el alquiler.'],
      just_cause_eviction: ['Desalojo con causa justificada', 'Límites a cuándo un arrendador puede terminar un arrendamiento.'],
      security_deposits: ['Depósitos de seguridad', 'Topes, manejo y devolución de los depósitos.'],
      application_screening_fees: ['Cargos de solicitud y de verificación', 'Lo que un arrendador puede cobrar por solicitar o ser evaluado.'],
      screening_restrictions: ['Restricciones en la selección de inquilinos', 'Límites a lo que se puede considerar al elegir inquilinos.'],
      algorithmic_rent_setting: ['Fijación algorítmica de alquileres', 'Normas sobre programas que recomiendan o fijan alquileres.'],
    },
    st: { applies: 'Aplica', unknown: 'Desconocido', superseded: 'Reemplazada', not_yet_effective: 'Aún no vigente', pending: 'Pendiente' },
    stHelp: { applies: 'Nuestras fuentes dicen que esta norma cubre esta dirección en esta fecha.', unknown: 'No podemos saberlo: falta un dato necesario.', superseded: 'Una norma de otro nivel tiene prioridad aquí.', not_yet_effective: 'Aprobada, pero no vigente en esta fecha.', pending: 'Un proyecto de ley que aún no es ley.' },
  },
};

/* ---------- state ---------- */
const S = { lang: 'en', asof: DEFAULT_ASOF, addr: null, tab: 'lookup', data: null, index: [], showAll: {}, prev: null };
const t = (k, ...a) => { const v = I18N[S.lang][k]; return typeof v === 'function' ? v(...a) : v; };
const L = () => LABELS[S.lang];
const isDate = s => /^\d{4}-\d{2}-\d{2}$/.test(s || '');
// text that exists only in English in the data: tag it so screen readers pronounce it right
const en = txt => S.lang === 'es' ? h('span', { lang: 'en' }, txt) : txt;

function saveHash() {
  const p = new URLSearchParams({ tab: S.tab, lang: S.lang, asof: S.asof });
  if (S.addr) p.set('addr', S.addr);
  try { history.replaceState(null, '', '#' + p.toString()); } catch (e) { /* file: pages */ }
}
function loadHash() {
  const p = new URLSearchParams(location.hash.slice(1));
  if (['lookup', 'changes', 'how'].includes(p.get('tab'))) S.tab = p.get('tab');
  if (['en', 'es'].includes(p.get('lang'))) S.lang = p.get('lang');
  else if ((navigator.language || '').toLowerCase().startsWith('es')) S.lang = 'es';
  if (isDate(p.get('asof'))) S.asof = p.get('asof');
  if (p.get('addr')) S.addr = p.get('addr');
}

/* ---------- data ---------- */
async function loadData() {
  const url = new URLSearchParams(location.search).has('sample') ? 'data/sample.json' : 'data/lookups_detail.json';
  const bar = $('#loading-bar');
  const res = await fetch(url);
  if (!res.ok) throw new Error(url + ' ' + res.status);
  const total = +res.headers.get('content-length') || 0;
  const chunks = []; let got = 0;
  const rd = res.body && res.body.getReader ? res.body.getReader() : null;
  if (!rd) return JSON.parse(await res.text());
  for (;;) {
    const { done, value } = await rd.read();
    if (done) break;
    chunks.push(value); got += value.length;
    // with gzip, content-length is the compressed size: show a bar only while it stays plausible
    if (total && got <= total) bar.value = Math.round(100 * got / total); else bar.removeAttribute('value');
    $('#loading-text').textContent = t('loading_mb', (got / 1e6).toFixed(1), total && got <= total ? (total / 1e6).toFixed(1) : '');
  }
  const buf = new Uint8Array(got); let o = 0;
  for (const c of chunks) { buf.set(c, o); o += c.length; }
  return JSON.parse(new TextDecoder().decode(buf));
}
function buildIndex(d) {
  S.index = Object.entries(d.addresses).map(([id, a]) => ({
    id, street: a.street_address || '', city: a.postal_city || '', state: a.state || '',
    hay: `${id} ${a.street_address} ${a.postal_city} ${a.state} ${a.zip || ''}`.toLowerCase(),
  }));
}
function resolveAt(res, date) {
  let cur = null;
  for (const e of res.timeline) { if (e.from <= date) cur = e; else break; }
  return cur && cur.result !== 'not_covered' ? cur : null;
}
// Spanish field with English fallback; tag English text when shown inside Spanish UI
const lf = (o, f) => (S.lang === 'es' && o[f + '_es']) ? o[f + '_es'] : o[f];
const lfEn = (o, f) => (S.lang === 'es' && !o[f + '_es']) ? en(o[f]) : lf(o, f);
const calm = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
const reveal = el => el && el.scrollIntoView({ behavior: calm() ? 'auto' : 'smooth', block: 'start' });
const fillAsof = txt => (txt || '').split('{ASOF}').join(S.asof);

/* ---------- typeahead ---------- */
let suggItems = [], suggActive = -1;
function suggest() {
  const q = $('#q').value.trim().toLowerCase();
  const ul = $('#sugg'); ul.replaceChildren(); suggActive = -1;
  if (!q) { closeSugg(); return; }
  const toks = q.split(/\s+/);
  suggItems = S.index.filter(a => toks.every(k => a.hay.includes(k)))
    .sort((a, b) => (b.id.toLowerCase() === q) - (a.id.toLowerCase() === q) || (b.street.toLowerCase().startsWith(q)) - (a.street.toLowerCase().startsWith(q)) || a.id.localeCompare(b.id))
    .slice(0, 8);
  if (!suggItems.length) ul.append(h('li', { role: 'option', 'aria-disabled': 'true', id: 'sg-none' }, t('no_match')));
  suggItems.forEach((a, i) => ul.append(h('li', { role: 'option', id: 'sg-' + i, 'aria-selected': 'false', onmousedown: ev => { ev.preventDefault(); pick(a.id); } },
    `${a.street}`, h('span', { class: 'sub' }, `${a.id} · ${a.city}, ${a.state}`))));
  ul.hidden = false; $('#q').setAttribute('aria-expanded', 'true');
}
function closeSugg() { $('#sugg').hidden = true; $('#q').setAttribute('aria-expanded', 'false'); $('#q').removeAttribute('aria-activedescendant'); }
function moveSugg(d) {
  if (!suggItems.length) return;
  suggActive = (suggActive + d + suggItems.length) % suggItems.length;
  [...$('#sugg').children].forEach((li, i) => li.setAttribute('aria-selected', i === suggActive ? 'true' : 'false'));
  $('#q').setAttribute('aria-activedescendant', 'sg-' + suggActive);
  $('#sugg').children[suggActive].scrollIntoView({ block: 'nearest' });
}
function pick(id) {
  S.addr = id; const a = S.data.addresses[id];
  $('#q').value = `${a.street_address}, ${a.postal_city}, ${a.state} (${id})`;
  closeSugg(); render(); reveal($('#layout'));
}

/* ---------- lookup view ---------- */
function openAddress(id, asof, tab) {
  if (!S.data.addresses[id]) return;
  S.addr = id; if (asof && isDate(asof)) S.asof = asof; S.tab = tab || 'lookup';
  const a = S.data.addresses[id];
  $('#q').value = `${a.street_address}, ${a.postal_city}, ${a.state} (${id})`;
  render(); window.scrollTo(0, 0); $('#main').focus({ preventScroll: true });
}
function renderQuick() {
  const q = $('#quick');
  if (!q.children.length) QUICK.forEach(d => q.append(h('button', { type: 'button', class: 'chip qd', title: QUICK_NOTE[S.lang][d], onclick: () => { S.asof = d; render(); } }, h('span', { class: 'qdate' }, d), ' ', h('span', { class: 'qn' }, QUICK_NOTE[S.lang][d]))));
  [...q.children].forEach((b, i) => b.setAttribute('aria-pressed', String(QUICK[i] === S.asof)));
  [...q.children].forEach((b, i) => { const n = b.querySelector('.qn'); if (n) n.textContent = QUICK_NOTE[S.lang][QUICK[i]]; b.title = QUICK_NOTE[S.lang][QUICK[i]]; });  // keep nodes so keyboard focus survives
  $('#asof').value = S.asof; $('#asof-iso').textContent = S.asof;
}
// display only: "3515 FILLMORE ST" -> "3515 Fillmore St"; search text and data stay raw
const nice = s => (s || '').toLowerCase().replace(/\b[a-z]/g, c => c.toUpperCase()).replace(/\b(Ne|Nw|Se|Sw)\b/g, w => w.toUpperCase());
function fact(label, ...val) { return [h('dt', null, label), h('dd', null, ...val)]; }
function geoText(g) { return t('geo_' + g) || g || ''; }

function stat(label, value, note, cls) {
  return h('div', { class: 'stat' + (cls ? ' ' + cls : '') }, h('dt', null, label), h('dd', null, h('span', { class: 'sv' }, value), note ? h('span', { class: 'sn' }, note) : null));
}
function addressCard(id, a) {
  const f = a.facts || {}, st = a.stack || {};
  const units = f.units != null ? t('units_exact', f.units) : (f.units_min != null ? t('units_min', f.units_min) : t('units_none'));
  const unitsMissing = f.units == null, unk = L().st.unknown;
  const use = [f.use_description, f.use_code ? `(${f.use_code})` : ''].filter(Boolean).join(' ');
  const lvl = (k, v, none) => h('li', { class: none ? 'none' : null }, h('span', { class: 'lv' }, t(k) + ': '), h('span', { class: 'jv' }, v));
  if (factsOpen == null) factsOpen = matchMedia('(min-width: 981px)').matches;
  return [h('section', { class: 'card addr', 'aria-label': t('addr_facts') },
    h('p', { class: 'kicker' }, `${t('id')} ${id}`),
    h('h3', null, nice(a.street_address)), h('p', { class: 'addr-city' }, [a.postal_city, [a.state, a.zip].filter(Boolean).join(' ')].filter(Boolean).join(', ')),
    h('h4', { class: 'kicker facts-h' }, t('addr_facts')),
    h('dl', { class: 'stats-f' },
      f.year_built != null ? stat(t('year_built'), String(f.year_built)) : stat(t('year_built'), unk, t('year_missing'), 'is-missing is-word'),
      unitsMissing ? stat(t('units'), f.units_min != null ? `${f.units_min}+` : unk, [units, f.units_note && S.lang === 'en' ? h('span', { class: 'sx' }, f.units_note) : null], 'is-missing' + (f.units_min != null ? '' : ' is-word'))
        : stat(t('units'), String(f.units), units.replace(String(f.units), '').replace(/[()]/g, '').trim()),
      stat(t('use'), use || t('use_none'), null, 'is-text'))),
    h('details', { class: 'card addr-more', open: factsOpen, ontoggle: e => { factsOpen = e.target.open; } }, h('summary', null, t('addr_stack')),
      h('ol', { class: 'stack', 'aria-label': t('addr_stack') },
        lvl('state', st.state || a.state),
        lvl('county', st.county || t('county_none'), !st.county),
        lvl('city', st.city || t('city_none'), !st.city)),
      h('p', { class: 'small geo' }, h('strong', null, t('geocode') + ': '), geoText(st.geocode_status), st.notes ? ' ' : '', st.notes ? en(st.notes) : ''),
      st.matched_address ? h('p', { class: 'small muted matched' }, `${t('matched')}: ${st.matched_address}`) : null),
    h('div', { class: 'actions' },
      h('button', { type: 'button', class: 'btn', onclick: () => downloadReport(id) }, t('dl_json')),
      h('button', { type: 'button', class: 'btn alt', onclick: () => window.print() }, t('dl_print')))];
}
let factsOpen = null;
function statusKey(cls) {
  return h('div', { class: 'card legend' + (cls ? ' ' + cls : '') }, h('h3', { class: 'kicker' }, t('status_key')),
    h('dl', null, STATUSES.map(s => h('div', { class: 'lg' }, h('dt', null, h('span', { class: 'badge b-' + s }, icon(s), L().st[s])), h('dd', null, L().stHelp[s])))));
}

function confWord(c) { return c >= 0.8 ? t('conf_hi') : c >= 0.6 ? t('conf_mid') : t('conf_lo'); }
function levelName(l) { return { state: t('lvl_state'), county: t('lvl_county'), city: t('lvl_city') }[l] || t('lvl_local'); }

function likelyText(l, f) {
  const lab = l === 'not_covered' ? t('likely_not') : (L().st[l] || l);
  return t('likely', lab, f.use_description || '', f.units_min != null ? f.units_min : '5');
}
const MINI = ['superseded', 'not_yet_effective', 'pending'];
function ruleCard(res, entry, rule, facts, was) {
  const status = entry.result;
  const pct = Math.round((res.confidence || 0) * 100);
  const text = S.lang === 'es' ? (entry.explanation_es || entry.explanation) : entry.explanation;
  const origin = (rule.source_doc_id || '')[0] === 'D' ? 'D' : 'X';
  const flag = entry.conflict_flag != null ? entry.conflict_flag : res.conflict_flag;
  const missing = res.missing_facts || [];
  // superseded, not-yet-effective and pending rules fold into one line unless flagged or just changed
  const mini = MINI.includes(status) && !flag && !was;
  const badge = h('span', { class: 'badge b-' + status, title: L().stHelp[status] }, icon(status), L().st[status]);
  const level = h('span', { class: 'level' }, `${levelName(rule.level)} · ${rule.jurisdiction}`);
  const body = [
    mini ? null : h('div', { class: 'rule-top' }, h('div', { class: 'rule-badges' }, badge,
      res.low_confidence ? h('span', { class: 'badge b-low' }, icon('flag'), t('lowconf')) : null,
      was ? h('span', { class: 'badge b-chg' }, t('changed', S.prev.asof, L().st[was] || t('was_none'))) : null), level),
    mini ? null : h('h4', null, lfEn(rule, 'title')),
    rule.requirement ? h('p', { class: 'req' }, lfEn(rule, 'requirement')) : null,
    rule.key_value ? h('div', { class: 'keyfig' }, h('span', { class: 'kl' }, t('key_fig')), h('span', { class: 'key' }, lfEn(rule, 'key_value'))) : null,
    h('p', { class: 'reason' }, h('strong', null, t('reason') + ' '), fillAsof(text)),
    entry.likely ? h('p', { class: 'likely small muted' }, likelyText(entry.likely, facts)) : null,
    missing.length ? h('div', { class: 'why' }, icon('unknown'), h('div', null, h('strong', null, t('why_missing') + ': '), missing.join('; '))) : null,
    flag ? h('div', { class: 'flag', role: 'note' }, icon('flag'), h('div', null, h('strong', null, t('flag_title') + ' '), res.conflict_note ? en(res.conflict_note) : '')) : null,
    rule.quoted_span || rule.citation ? h('figure', { class: 'cite' },
      rule.quoted_span ? [h('span', { class: 'kl' }, t('quote')), h('blockquote', { lang: 'en' }, rule.quoted_span)] : null,
      rule.citation ? h('figcaption', null, h('span', { class: 'kl' }, t('citation')), ' ', h('span', { lang: 'en' }, rule.citation)) : null) : null,
    h('div', { class: 'rule-foot' }, h('div', { class: 'meter', title: t('conf_note') }, h('span', null, `${t('conf')}: ${pct}% (${confWord(res.confidence || 0)})`),
      h('span', { class: 'track', role: 'meter', 'aria-valuemin': '0', 'aria-valuemax': '100', 'aria-valuenow': String(pct), 'aria-label': t('conf') }, h('span', { class: 'fill', style: `width:${pct}%` }))),
    h('details', null, h('summary', null, t('source'), h('span', { class: 'src-tag' }, t('origin_' + origin))),
      h('dl', null,
        h('dt', null, t('link')), h('dd', null, rule.source_url ? h('a', { href: rule.source_url, target: '_blank', rel: 'noopener noreferrer' }, rule.source_url) : ''),
        h('dt', null, t('retrieved')), h('dd', null, (rule.retrieved_at || '').slice(0, 10)),
        h('dt', null, t('doc_id')), h('dd', null, rule.source_doc_id || ''),
        h('dt', null, t('origin')), h('dd', null, t('origin_' + origin)),
        h('dt', null, t('rule_status')), h('dd', null, `${STATUS_NAME[S.lang][rule.status] || rule.status || ''}; ${t('eff')}: ${rule.effective_date || t('no_eff')}`),
        res.facts_used && res.facts_used.length ? [h('dt', null, t('facts_used')), h('dd', null, res.facts_used.map(f => FACT_NAME[S.lang][f] || f.replace(/_/g, ' ')).join(', '))] : null),
      h('p', { class: 'small muted' }, t('src_caveat'))))];
  if (mini) return h('details', { class: 'rule rule-mini anim s-' + status },
    h('summary', null, badge, h('span', { class: 'rm-t' }, lfEn(rule, 'title')), level, rule.key_value ? h('span', { class: 'rm-k' }, lfEn(rule, 'key_value')) : null),
    h('div', { class: 'rule-body' }, body));
  return h('article', { class: 'rule anim s-' + status + (was ? ' changed' : '') }, body);
}

function catNotes(a, cat) {
  const D = S.data, st = a.stack || {};
  const here = new Set([st.state || a.state, st.city].filter(Boolean));
  return {
    noRule: (D.no_rule || []).filter(n => n.category === cat && here.has(n.jurisdiction)),
    gaps: (D.gaps || []).filter(n => n.category === cat && here.has(n.jurisdiction)),
  };
}
function noteBlocks(n) {
  const one = (x, plain) => h('div', { class: 'empty' }, h('p', null, h('strong', null, `${x.jurisdiction}: `), plain),
    x.note ? h('details', null, h('summary', null, t('reviewers')), h('p', { class: 'small', lang: 'en' }, x.note)) : null);
  return [...n.noRule.map(x => one(x, t('no_rule_plain'))), ...n.gaps.map(x => one(x, t('gap_plain')))];
}

function renderAnswer() {
  const box = $('#answer'), rail = $('#rail-addr'); box.replaceChildren(); rail.replaceChildren();
  const has = !!(S.addr && S.data.addresses[S.addr]);
  $('#view-lookup').classList.toggle('has-addr', has);
  if (!has) {
    rail.append(statusKey());
    box.append(h('p', { class: 'lede' }, t('pick_hint')),
      h('div', { class: 'examples' }, h('h3', { class: 'kicker' }, t('try_ex')), h('ul', { class: 'exlist' }, EXAMPLES.filter(id => S.data.addresses[id]).map((id, i) => {
        const x = S.data.addresses[id];
        return h('li', null, h('button', { type: 'button', class: 'ex anim', style: `--i:${i}`, onclick: () => pick(id) },
          h('span', { class: 'ex-id' }, id), h('span', { class: 'ex-st' }, nice(x.street_address)), h('span', { class: 'qn' }, `${x.postal_city}, ${x.state}`)));
      }))),
      h('section', { class: 'cats-box', 'aria-labelledby': 'h-cats' }, h('h3', { class: 'kicker', id: 'h-cats' }, t('cats_h')),
        h('ol', { class: 'cats' }, CATS.map((c, i) => h('li', null, h('span', { class: 'cat-n', 'aria-hidden': 'true' }, String(i + 1).padStart(2, '0')),
          h('span', null, h('b', null, L().cat[c][0]), h('span', { class: 'small muted' }, L().cat[c][1])))))));
    $('#live').textContent = ''; S.prev = null; return;
  }
  const a = S.data.addresses[S.addr], D = S.data;
  rail.append(...addressCard(S.addr, a));
  const byCat = {}; const counts = {}; const now = {}; let n = 0;
  for (const res of a.results) {
    const e = resolveAt(res, S.asof); if (!e) continue;
    const rule = D.rules[res.team_rule_id]; if (!rule) continue;
    (byCat[res.category] = byCat[res.category] || []).push({ res, e, rule });
    counts[e.result] = (counts[e.result] || 0) + 1; n++; now[res.team_rule_id] = e.result;
  }
  // highlight what moved since the previous date shown for the same address
  const P = S.prev && S.prev.addr === S.addr && S.prev.asof !== S.asof ? S.prev : null;
  const was = rid => P && P.m[rid] !== now[rid] ? (P.m[rid] || 'none') : null;
  const nChg = P ? Object.keys(now).filter(was).length : 0;
  const order = STATUSES.reduce((o, s, i) => (o[s] = i, o), {});
  for (const cat of CATS) (byCat[cat] || []).sort((x, y) => order[x.e.result] - order[y.e.result]);
  box.append(h('div', { class: 'res-head' },
    h('h3', null, t('shown', n, S.asof)),
    h('div', { class: 'tally', 'aria-hidden': 'true' }, STATUSES.filter(s => counts[s]).map(s => h('span', { class: 's-' + s, style: `flex-grow:${counts[s]}` }))),
    h('div', { class: 'summary' }, STATUSES.filter(s => counts[s]).map(s => h('span', { class: 'badge b-' + s }, icon(s), `${L().st[s]}: ${counts[s]}`)),
      nChg ? h('span', { class: 'badge b-chg' }, t('n_changed', nChg, P.asof)) : null),
    ),
    h('h4', { class: 'glance-h kicker' }, t('glance')),
    h('div', { class: 'glance' }, CATS.map((cat, i) => {
      const items = byCat[cat] || [], top = items[0], notes = catNotes(a, cat);
      const st = top ? top.e.result : 'none';
      const label = top ? L().st[st] : (notes.gaps.length && !notes.noRule.length ? t('glance_gap') : t('glance_none'));
      // other statuses in the category, spelled out (for example "+1 Superseded")
      const rest = {}; items.slice(1).forEach(x => { if (x.e.result !== st) rest[x.e.result] = (rest[x.e.result] || 0) + 1; });
      return h('button', { type: 'button', class: `tile anim s-${st}${items.some(x => was(x.res.team_rule_id)) ? ' changed' : ''}`, style: `--i:${i}`,
        onclick: () => { const el = $('#c-' + cat); reveal(el); el.focus({ preventScroll: true }); } },
        h('span', { class: 'tnum', 'aria-hidden': 'true' }, String(i + 1).padStart(2, '0')),
        h('span', { class: 'tmain' }, h('span', { class: 'tn' }, L().cat[cat][0], items.length > 1 ? h('span', { class: 'qn muted' }, ` · ${t('n_rules_short', items.length)}`) : null),
          top && top.rule.key_value ? h('span', { class: 'tk' }, lfEn(top.rule, 'key_value')) : null),
        h('span', { class: 'tb' }, h('span', { class: 'badge b-' + (top ? st : 'none') }, top ? icon(st) : null, label),
          Object.keys(rest).map(s => h('span', { class: 'tmore s-' + s }, `+${rest[s]} ${L().st[s]}`)),
          items.some(x => x.e.conflict_flag != null ? x.e.conflict_flag : x.res.conflict_flag) ? h('span', { class: 'badge b-low', title: t('flag_title') }, icon('flag'), t('flag_short')) : null),
        h('span', { class: 'tchev', 'aria-hidden': 'true' }));
    })),
    h('p', { class: 'small muted caveat-g' }, t('asof_on', S.asof) + '. ' + t('src_caveat')),
    statusKey('legend-inline'));
  CATS.forEach((cat, ci) => {
    const items = byCat[cat] || [];
    const notes = catNotes(a, cat); const [name, desc] = L().cat[cat];
    const sec = h('section', { class: 'cat', 'aria-labelledby': 'c-' + cat },
      h('div', { class: 'cat-head' }, h('span', { class: 'cat-n', 'aria-hidden': 'true' }, String(ci + 1).padStart(2, '0')),
        h('div', null, h('h3', { id: 'c-' + cat, tabindex: '-1' }, `${name} `, h('span', { class: 'cnt' }, `(${items.length})`)), h('p', { class: 'desc' }, desc))));
    if (items.length) {
      items.forEach(i => sec.append(ruleCard(i.res, i.e, i.rule, a.facts || {}, was(i.res.team_rule_id))));
      const nb = noteBlocks(notes);
      if (nb.length) sec.append(h('details', null, h('summary', null, t('also', nb.length)), nb));
    } else {
      const nb = noteBlocks(notes);
      sec.append(...(nb.length ? nb : [h('div', { class: 'empty' }, h('p', null, h('strong', null, t('nothing_h'))), h('p', { class: 'small' }, t('nothing_sub')))]));
    }
    box.append(sec);
  });
  $('#live').textContent = t('live_update', n, S.asof, a.street_address) + (nChg ? ' ' + t('n_changed', nChg, P.asof) + '.' : '');
  if (!S.prev || S.prev.addr !== S.addr || S.prev.asof !== S.asof) S.prev = { addr: S.addr, asof: S.asof, m: now };
}

function downloadReport(id) {
  const a = S.data.addresses[id], D = S.data, rules = [];
  for (const res of a.results) {
    const e = resolveAt(res, S.asof), r = D.rules[res.team_rule_id]; if (!e || !r) continue;
    rules.push({
      category: res.category, result: e.result, title: r.title, title_es: r.title_es, jurisdiction: r.jurisdiction,
      requirement: r.requirement, requirement_es: r.requirement_es, key_value: r.key_value, key_value_es: r.key_value_es,
      address_reasoning: fillAsof(e.explanation), address_reasoning_es: fillAsof(e.explanation_es), as_of: S.asof,
      conflict_flag: e.conflict_flag != null ? e.conflict_flag : res.conflict_flag, conflict_note: res.conflict_note,
      confidence: res.confidence, missing_facts: res.missing_facts,
      citation: r.citation, quoted_span: r.quoted_span, source_url: r.source_url, source_doc_id: r.source_doc_id, retrieved_at: r.retrieved_at,
    });
  }
  const rep = { not_legal_advice: D.not_legal_advice || 'Not legal advice.', as_of: S.asof, data_generated_at: D.generated_at, address_id: id, address: a.street_address, postal_city: a.postal_city, state: a.state, facts: a.facts, stack: a.stack, rules };
  const url = URL.createObjectURL(new Blob([JSON.stringify(rep, null, 2)], { type: 'application/json' }));
  const l = h('a', { href: url, download: `${t('download_name')}_${id}_${S.asof}.json` });
  document.body.append(l); l.click(); l.remove(); setTimeout(() => URL.revokeObjectURL(url), 2000);
}
let reopen = [];
window.addEventListener('beforeprint', () => { reopen = [...document.querySelectorAll('details:not([open])')]; reopen.forEach(d => d.open = true); });
window.addEventListener('afterprint', () => { reopen.forEach(d => d.open = false); reopen = []; });

/* ---------- what changed ---------- */
function addrList(ids, asof, key) {
  const ok = ids.filter(i => S.data.addresses[i]);
  const lim = S.showAll[key] ? ok.length : 40;
  const ul = h('ul', { class: 'alist' }, ok.slice(0, lim).map(id => {
    const a = S.data.addresses[id];
    return h('li', null, h('button', { type: 'button', onclick: () => openAddress(id, asof, 'lookup') }, h('strong', null, id), h('span', null, `${nice(a.street_address)}, ${a.postal_city}`)));
  }));
  const more = ok.length > lim ? h('button', { type: 'button', class: 'btn alt', onclick: () => { S.showAll[key] = true; renderChanges(); } }, t('show_all', ok.length)) : null;
  return h('div', null, ul, more);
}
function countBadges(obj) {
  return Object.entries(obj || {}).map(([k, v]) => h('span', { class: 'badge b-' + (STATUSES.includes(k) ? k : 'pending') }, STATUSES.includes(k) ? icon(k) : null, `${L().st[k] || k}: ${v}`));
}
function renderChanges() {
  const D = S.data, v = $('#view-changes'); v.replaceChildren();
  v.append(h('div', { class: 'hero hero-page' }, h('div', { class: 'hero-txt' }, h('h2', { id: 'h-changes' }, t('h_changes')), h('p', { class: 'muted' }, t('changes_intro')),
    S.lang === 'es' ? h('p', { class: 'small muted' }, t('title_en_note')) : null)));
  const pd = (lab, d) => h('p', { class: 'pd' }, h('span', { class: 'kl' }, lab + ' '), h('span', { class: 'dt' }, d));
  Object.entries(D.tests || {}).sort().forEach(([id, T], ti) => {
    const date = T.as_of_after || T.as_of || S.asof;
    const ruleLis = (T.team_rule_ids || []).map(r => D.rules[r]).filter(Boolean).map(r => h('li', null, en(r.title), ` (${r.citation || ''}, ${r.jurisdiction})`));
    const sec = h('article', { class: 'card test', style: `--i:${ti}` },
      h('div', { class: 'test-head' }, h('span', { class: 'tid', 'aria-hidden': 'true' }, id),
        h('div', null, h('p', { class: 'kicker' }, t('type_' + T.type) || T.type), h('h3', null, h('span', { class: 'sr' }, `${id}: `), en(T.title)))),
      h('p', { class: 'test-sum' }, TEST_SUMMARY[S.lang][id] || ''));
    const pairs = h('div', { class: 'pairs' });
    if (T.as_of_before) pairs.append(h('div', { class: 'pair' }, pd(t('t_before'), T.as_of_before), h('div', { class: 'pb' }, countBadges(T.counts_before))),
      h('span', { class: 'arrow', 'aria-hidden': 'true' }, '→'),
      h('div', { class: 'pair' }, pd(t('t_after'), T.as_of_after), h('div', { class: 'pb' }, countBadges(T.counts_after))));
    else pairs.append(h('div', { class: 'pair' }, T.as_of ? pd(t('t_date'), T.as_of) : null, h('div', { class: 'pb' }, countBadges(T.counts))));
    const left = h('div', null, h('h4', null, t('t_counts')), pairs);
    if (ruleLis.length) left.append(h('h4', null, t('t_rules')), h('ul', { class: 'plain' }, ruleLis));
    const right = h('div', null);
    const city = Object.entries(T.affected_by_city || {});
    if (city.length) {
      const max = Math.max(...city.map(c => c[1]));
      right.append(h('h4', null, t('t_city')), ...city.map(([c, n]) => h('div', { class: 'bar-row' }, h('span', null, c), h('span', { class: 'bg', 'aria-hidden': 'true' }, h('span', { style: `width:${Math.round(100 * n / max)}%` })), h('span', { class: 'num' }, String(n)))));
    }
    sec.append(h('div', { class: 'test-grid' + (city.length ? '' : ' one') }, left, city.length ? right : null));
    const aff = T.affected_address_ids || [];
    sec.append(h('h4', null, t('t_affected', aff.length)));
    if (aff.length) sec.append(h('p', { class: 'small muted' }, t('t_opens', date)), addrList(aff, date, id + 'a')); else sec.append(h('p', { class: 'muted' }, t('t_empty')));
    const cf = T.conflict_flag_address_ids || [];
    if (cf.length) sec.append(h('details', null, h('summary', null, t('t_conflict', cf.length)), addrList(cf, date, id + 'c')));
    v.append(sec);
  });
}

/* ---------- how it works ---------- */
function renderHow() {
  const D = S.data, A = D.audit || {}, v = $('#view-how'); v.replaceChildren();
  const src = A.sources || [], nd = src.filter(s => s.doc_id[0] === 'D').length;
  const val = A.validation || {};
  const stat = (l, x, wide) => h('div', { class: wide ? 'wide' : null }, h('dt', null, l), h('dd', null, x));
  const list = k => h('ul', { class: 'plain' }, I18N[S.lang][k].map(x => h('li', null, x)));
  v.append(h('div', { class: 'hero hero-page' }, h('div', { class: 'hero-txt' }, h('h2', { id: 'h-how' }, t('h_how')), h('p', { class: 'muted' }, t('how_intro')))));
  v.append(h('h3', { class: 'sec-h' }, t('h_valid')), h('dl', { class: 'stats anim' },
    stat(t('n_addr'), String(Object.keys(D.addresses).length)), stat(t('n_rules'), String(Object.keys(D.rules).length)),
    stat(t('valid_rules'), String(val.rules || '')), stat(t('valid_quotes'), String(val.quotes_found || '')),
    stat(t('n_runs'), String((A.runs || []).length)), stat(t('gen'), D.generated_at || '', true)));
  v.append(h('h3', { class: 'sec-h' }, t('h_pipe')), h('ol', { class: 'pipe' }, I18N[S.lang].pipe.map(p => h('li', null, h('b', null, p[0]), h('span', null, p[1]), h('span', { class: 'small code' }, p[2])))));
  v.append(h('div', { class: 'how-grid' },
    h('section', { class: 'card' }, h('h3', null, t('h_extract')), list('extract')),
    h('section', { class: 'card guard' }, h('h3', null, t('h_guard')), list('guard')),
    h('section', { class: 'card limits' }, h('h3', null, t('h_limits')), list('limits')),
    h('section', { class: 'card' }, h('h3', null, t('h_scale')), list('scale'))));
  v.append(h('h3', { class: 'sec-h' }, t('h_sources')), h('p', { class: 'small muted' }, t('src_count', src.length, nd, src.length - nd)),
    h('div', { class: 'scroll' }, h('table', null, h('thead', null, h('tr', null, I18N[S.lang].src_cols.map(c => h('th', { scope: 'col' }, c)))),
      h('tbody', null, src.map(s => h('tr', null, h('td', null, s.doc_id), h('td', null, t('origin_' + (s.doc_id[0] === 'D' ? 'D' : 'X'))),
        h('td', { style: 'overflow-wrap:anywhere' }, h('a', { href: s.url, target: '_blank', rel: 'noopener noreferrer' }, s.url)), h('td', { class: 'nowrap' }, (s.retrieved_at || '').slice(0, 10))))))));
  const runs = (A.runs || []).slice(-30);
  if (runs.length) v.append(h('details', null, h('summary', null, t('h_runs')), h('div', { class: 'scroll' }, h('table', null,
    h('tbody', null, runs.map(r => h('tr', null, h('td', null, r.ts), h('td', null, `${r.stage} / ${r.actor}`), h('td', { class: 'small', style: 'overflow-wrap:anywhere' }, JSON.stringify(r.detail)))))))));
}

/* ---------- shell ---------- */
function applyLang() {
  document.documentElement.lang = S.lang;
  document.title = t('title');
  document.querySelectorAll('[data-i18n]').forEach(el => { el.textContent = t(el.dataset.i18n); });
  document.querySelectorAll('.lang').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.lang === S.lang)));
  $('#q').placeholder = S.lang === 'es' ? '3515 Fillmore, A0002, Hoboken...' : '3515 Fillmore, A0002, Hoboken...';
  $('.langs').setAttribute('aria-label', S.lang === 'es' ? 'Idioma' : 'Language');
  $('#quick').setAttribute('aria-label', S.lang === 'es' ? 'Fechas rápidas' : 'Quick dates');
  $('.tabs').setAttribute('aria-label', S.lang === 'es' ? 'Secciones' : 'Sections');
}
function render() {
  applyLang();
  document.querySelectorAll('.tab').forEach(b => b.setAttribute('aria-current', b.dataset.tab === S.tab ? 'page' : 'false'));
  ['lookup', 'changes', 'how'].forEach(k => { $('#view-' + k).hidden = k !== S.tab || !S.data; });
  if (S.data) {
    $('#foot-text').textContent = t('foot', S.data.generated_at || '');
    renderQuick();
    if (S.tab === 'lookup') renderAnswer(); else if (S.tab === 'changes') renderChanges(); else renderHow();
  }
  saveHash();
}

function init() {
  loadHash();
  document.querySelectorAll('.tab').forEach(b => b.addEventListener('click', () => { S.tab = b.dataset.tab; render(); window.scrollTo(0, 0); }));
  document.querySelectorAll('.lang').forEach(b => b.addEventListener('click', () => { S.lang = b.dataset.lang; render(); }));
  $('#asof').addEventListener('change', e => { if (isDate(e.target.value)) { S.asof = e.target.value; render(); } });
  const q = $('#q');
  q.addEventListener('input', suggest);
  q.addEventListener('focus', () => { if (q.value.trim() && !/\(A\d+\)$/.test(q.value)) suggest(); });
  q.addEventListener('blur', closeSugg);
  q.addEventListener('keydown', e => {
    if (e.key === 'ArrowDown') { e.preventDefault(); if ($('#sugg').hidden) suggest(); moveSugg(1); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); moveSugg(-1); }
    else if (e.key === 'Enter') { if (suggActive >= 0) { e.preventDefault(); pick(suggItems[suggActive].id); } else if (suggItems.length && !$('#sugg').hidden) { e.preventDefault(); pick(suggItems[0].id); } }
    else if (e.key === 'Escape') closeSugg();
  });
  window.addEventListener('hashchange', () => {
    const tab = S.tab; loadHash(); if (S.tab !== tab) window.scrollTo(0, 0);
    if (S.data) { const a = S.data.addresses[S.addr]; if (a) q.value = `${a.street_address}, ${a.postal_city}, ${a.state} (${S.addr})`; render(); }
  });
  applyLang();
  loadData().then(d => {
    S.data = d; buildIndex(d); $('#loading').hidden = true;
    if (S.addr && d.addresses[S.addr]) { const a = d.addresses[S.addr]; q.value = `${a.street_address}, ${a.postal_city}, ${a.state} (${S.addr})`; } else S.addr = null;
    render();
  }).catch(err => {
    $('#loading').hidden = true;
    const f = $('#fatal'); f.hidden = false; f.textContent = t('load_fail') + err.message;
  });
}
init();
