from tqdm import tqdm
import json, random

# Para crear documentación: pdoc --html src/utils.py --force

def save_dict(dic, file):
    """Guarda diccionario como json.
    
    Args
    ----------
    dic : dict
        Diccionario a guardar.
    file : str
        Archivo de salida.
    """
    with open(file, 'w') as fp:
        json.dump(dic, fp)

def load_dict(file):
    """Carga json como diccionario.
    
    Args
    ----------
    file : dict
        Archivo json.

    Returns
    -------
    dict
        Diccionario.
    """
    with open(file, 'r') as fp:
        return json.load(fp)
    
def load_dicts(files):
    """Carga y une múltiples archivos json en un diccionario.
    
    Args
    ----------
    files : list
        Lista de archivos json.

    Returns
    -------
    dict
        Diccionario.
    """
    res = {}
    for file in files:
        res.update(load_dict(file))
    return res

def df_to_dict(df):
    """Convierte DF en diccionario con listas.
    
    Args
    ----------
    df : pd.DataFrame
        DataFrame.

    Returns
    -------
    dict
        Diccionario donde las `keys` son los nombres columnas y los `values` son las columnas (como listas).
    """
    res = {}
    for c in df.columns:
        res[c] = df[c].tolist()
    return res

def words_with_word(drae, target_word):
    """Lista de todas las palabras que contienen `target_word` en su definición.

    Args
    ----------
    drae : dict
        Diccionario de la RAE.
    target_word : str
        Palabra que comprobar.

    Returns
    -------
    list
        Lista de tuplas: `(palabra, acepción)`
    """
    target_id = drae[target_word]['id']
    res = []
    for word in drae:
        for i in range(len(drae[word]['defs'])): # Para cada acepción
            rel_ids = drae[word]['rel_ids'][i]
            if target_id in '|'.join(rel_ids): # Si el 'target_id' está en la acepción, añadir palabra y acepción
                res.append((word, drae[word]['defs'][i]))
                break # Con que una acepción tenga la palabra, `word` ya queda registrada (además, con su acepción más común)
    return res

def get_kinds(drae, word):
    """Tipos de la palabra según sus definiciones.

    Args
    ----------
    drae : dict
        Diccionario de la RAE.
    word : str
        Palabra a buscar en su forma diccionario (ej. `fresa1`).

    Returns
    -------
    list
        Lista con los tipos de la palabra.
    """
    abrev = ABREV
    kinds = {}
    for kind in ABREV:
        for abr in abrev[kind]:
            kinds[abr] = kind
    res = []
    for d in drae[word]['defs']:
        start = d.split('. ')[1] + '.'
        if start in kinds and kinds[start] not in res: # Abreviatura está y no está registrado el tipo
            res.append(kinds[start])
    return res

def leave_single_kind(df):
    """Deja únicamente palabras de 1 tipo (incluyendo polisemia y homonimia).

    Args
    ----------
    df : pd.DataFrame
        DataFrame de palabras.

    Returns
    -------
    pd.DataFrame
        DataFrame de palabras con sólo 1 tipo.
    """
    # Reducir en homonimia
    aux = df.groupby('simple_word')['kinds'].nunique().reset_index()
    aux = aux[aux['kinds'] == 1] # Palabras con sólo 1 tipo
    df = df[df['simple_word'].isin(aux['simple_word'])] # Dejar sólo las que tengan 1 tipo
    # Reducir en polisemia (procesar después, porque si no palabras como `fresa` permanecen)
    df = df[~df['kinds'].str.contains(',')] # Eliminar las que tengan `,` en el tipo
    return df

def set_commonness(row):
    """Determina cuánto de común es una palabra en un rango del 0 (muy rara) al 4 (común).

    Args
    ----------
    row : pd.Series
        Fila de una palabra.

    Returns
    -------
    int
        Nivel de común.
    """
    if row['def_perc'] >= 95: # Palabras comodín (aparecen en muchas definiciones)
        return 4
    if row['crea_perc'] >= 80 and row['ngram_perc'] >= 80: # Muy frecuente
        return 3
    if row['crea_perc'] >= 50 and row['ngram_perc'] >= 50: # Menos frecuente
        return 2
    if (row['crea_perc'] >= 30 and row['ngram_perc'] >= 30) or row['def_freq'] >= 5: # Menos frecuente aún o no tan frecuente pero aparece en más de 5 definiciones
        return 1
    return 0 # Casi no aparece como palabra

def exclude_group(drae, group):
    """Excluye acepciones que pertenecen a un grupo determinado de tecnicismos (p. ej. regionalismos).

    Args
    ----------
    drae : dict
        Diccionario de la RAE.
    group : list
        Grupo de abreviaturas que se quieren eliminar.

    Returns
    -------
    dict
        Diccionario con términos del grupo excluídos. Si una palabra pierde todas sus acepciones se quita del diccionario.
    """
    words_to_remove = []
    for word in tqdm(drae):
        i = 0 # Índice de acepción a borrar
        j = 0 # Índice total de acepciones, para saber cuándo he llegado al final
        total_len = len(drae[word]['defs']) # Total de acepciones (en el momento inicial)
        while j < total_len:
            definition = drae[word]['defs'][i]
            deleted = False
            for term in group: # Para cada término a excluir
                if term in definition: # Si el término aparece en la acepción
                    del drae[word]['defs'][i]
                    del drae[word]['abrev'][i]
                    del drae[word]['rel_ids'][i]
                    deleted = True
                    break
            if not deleted:
                i += 1
            j += 1
        if len(drae[word]['defs']) == 0: # Si la palabra ha perdido todas las acepciones, eliminar palabra
            words_to_remove.append(word)
    for word in words_to_remove:
        del drae[word]
    return drae

def get_random_word(df, commonness=None, appear_lim=None):
    """Selecciona palabra aleatoria de rareza `commonness` y límite de acepciones `appear_lim`.

    Args
    ----------
    df : pd.DataFrame
        DataFrame de palabras.
    commonness : None or int
        Número del `1` al `4` (`0` y `5` suelen estar excluídos).
    appear_lim : None or int
        Número límite de acepciones en las que la palabra puede aparecer.

    Returns
    -------
    str
        Palabra aleatoria dentro de los parámetros datos.
    """
    temp = df.copy()
    # print(commonness, appear_lim)
    if commonness is not None: # Si la rareza está definida
        temp = df[df['commonness'] == commonness].copy()
    if appear_lim: # Si el límite apariciones está definido
        temp = temp[temp['def_freq'] >= appear_lim]
    return temp.sample(1)['word'].iloc[0]

def get_acep_num(acep): 
    """Número de la acepción.

    Args
    ----------
    acep : str
        Acepción objetivo.

    Returns
    -------
    int
        Número (ordinal) de la acepción.
    """
    try:
        num = acep.split('.')[0]
        return int(num)
    except:
        raise Exception('La acepción no contiene número')
        
def add_commonness(www, df):
    """Añade rareza a `www` (lista de soluciones).

    Args
    ----------
    www: list of tuple
        Lista de soluciones.
    df: pd.DataFrame
        DataFrame de palabras.

    Returns
    -------
    list of tuple
        Lista de tripletas `(palabra, acepción, rareza)`.
    """
    return [(word, acep, df[df['word'] == word]['commonness'].iloc[0]) for word, acep in www] # Asociar rareza a palabras encontradas

def limit_defs(www, limit_acep=None):
    """Limita el ordinal de las acepciones.

    Args
    ----------
    www: list of tuple
        Lista de soluciones.
    limit_acep: None or int
        Límite del ordinal de las acepciones.

    Returns
    -------
    list of tuple
        `www` con restricciones aplicadas.
    """
    return [(word, acep) for word, acep in www if get_acep_num(acep) <= limit_acep] # Limita a acepciones con ordinal menor o igual que 'limit_acep'

def pick_solutions(solutions, target_word, hints, avoid_common=False):
    """Decide si en las soluciones están las dificultades deseadas, en cuyo caso devuelve una muestra en orden para mostrar. La `target_word` no puede aparecer entre las soluciones.

    Args
    ----------
    solutions: list of tuple
        Lista de soluciones con rareza: [(palabra, definición, rareza)].
    target_word: str
        Palabra objetivo.
    hints: list
        Rareza de las pistas.
    avoid_common: bool
        Determina si eliminar candidatos que su deletreo inicial (primeras tres letras) coincida con la `target_word` (P. ej., 'pulmón' y 'pulmonar').

    Returns
    -------
    bool or list of tuple
        Devuelve una muestra de soluciones con las rarezas solicitadas. En caso de no ser posible devuelve `False`.
    """
    count = {h: hints.count(h) for h in set(hints)}
    sol_count = {h: [] for h in set(hints)}
    random.shuffle(solutions)
    for sol in solutions:
        diff = sol[-1]
        if diff in sol_count and len(sol_count[diff]) < count[diff] and sol[0] != target_word and (avoid_common and sol[0][:3] != target_word[:3]): # Si dificultad adecuada y límite no alcanzado y palabra no misma que la buscada e inicio de palabra no coincide
            sol_count[diff].append(sol)
    for h in sol_count:
        if len(sol_count[h]) < count[h]: # Si no hay suficientes pistas
            return False
    res = []
    for hint in hints:
        res.append(sol_count[hint].pop(0)) # Añade solución a la vez que la elimina del diccionario
    return res

def show_letter(word, index):
    """Muestra letra `index` de `word` (con texto de acompañamiento).

    Args
    ----------
    word : str
        Palabra a mostrar.
    index: int
        Índice de la letra a mostrar.
    """
    description = f"Letra {'primera' if index == 0 else ('última' if index == -1 else 'intermedia')}"
    prefix = '' if index == 0 else '_'
    suffix = '' if index == -1 else '_'
    print(f'{description}: {prefix}{word[index]}{suffix}')

def show_length(word):
    """Muestra longitud de `word` (con texto de acompañamiento).

    Args
    ----------
    word : str
        Palabra a mostrar.
    """
    infix = '*'*(len(word)-2)
    print(f'Aspecto: {word[0]}{infix}{word[-1]}')

def show_words(solutions, df, interval=(0,-1)):
    """Muestra el intervalo determinado de soluciones (con texto de acompañamiento).

    Args
    ----------
    solutions : list of tuple
        Lista de tripletas `(palabra, acepción, rareza)`.
    df: pd.DataFrame
        DataFrame de palabras.
    interval: tuple
        Pareja de índices de las soluciones a mostrar. Para cubrir todas ellas
    """
    start = interval[0]
    end = interval[-1] + (0 if interval[-1] > 0 else len(solutions)+1)
    for i, (word, definition, commonness) in enumerate(solutions):
        if start <= i and i < end:
            print(f"Palabra {i+1}: {df[df['word'] == word]['simple_word'].iloc[0]} ({'★'*commonness if commonness > 0 else '💀'})")
            
def show_content(solutions, df):
    """Muestra las acepciones de las soluciones (con texto de acompañamiento).

    Args
    ----------
    solutions : list of tuple
        Lista de tripletas `(palabra, acepción, rareza)`.
    """
    for i, (word, definition, commonness) in enumerate(solutions):
        print(f"Palabra {i+1}: {df[df['word'] == word]['simple_word'].iloc[0]} ({'★'*commonness if commonness > 0 else '💀'})")
        print(f" > {definition}\n")

def modify_def(target_word, definition, l=5):
    """Modifica la definición para ocultar target_word.

    Args
    ----------
    target_word : str
        Palabra objetivo.
    definition: str
        Definición a modificar.
    l: int
        Longitud de la comparación.

    Returns
    -------
    str
        Definición modificada.
    """
    modified_def = ''
    l = min(l, len(target_word) - 1) # Longitud de la comparación
    words_in_def = definition.replace(',', ' ,').replace('.', ' .').split(' ')
    for w in words_in_def:
        simplified_w = w.lower().replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u') # Eliminar tildes
        if simplified_w[:l] == target_word.lower().replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u')[:l]:
            modified_def += '■' + ' '
        else:
            modified_def += w + ' '
    return modified_def.replace(' ,', ',').replace(' .', '.')
            
ABR_VERB = ['aux.', 'copulat.', 'impers.', 'intr.', 'prnl.', 'tr.', 'part.'] # Verbos
ABR_SUST = ['f.', 'm.', 'n.'] # Sustantivos
ABR_ADJ = ['adj.'] # Adjetivos
ABR_ADV = ['adv.'] # Adverbios
ABR_PREP = ['prep.', 'contracc.'] # Preposiciones
ABR_ART = ['art.'] # Artículos
ABR_PRON = ['pron.'] # Pronombres
ABR_INTERJ = ['interj.'] # Interjeciones
ABR_CONJ = ['conj.'] # Conjunciones
ABR_ONOMAT = ['onomat.'] # Onomatopeyas
ABR_ELEM = ['elem.', 'pref.', 'suf.'] # Elementos compositivos
ABR_EXPR = ['expr.'] # Expresiones

ABREV = {'sust': ABR_SUST, 'verb': ABR_VERB, 'adj': ABR_ADJ, 'adv': ABR_ADV, 'prep': ABR_PREP, 'art': ABR_ART, 'pron': ABR_PRON, 'interj': ABR_INTERJ, 'conj': ABR_CONJ, 'onomat': ABR_ONOMAT, 'elem': ABR_ELEM, 'expr': ABR_EXPR}

ABECEDARIO = ['a1', 'be1', 'ce1', 'de1', 'e1', 'efe', 'ge1', 'hache', 'i', 'jota1', 'ka', 'ele1', 'eme1', 'ene', 'eñe', 'o1', 'pe', 'cu1', 'erre1', 'ese1', 'te1', 'u1', 'uve', 'equis', 'y', 'zeta1']

STOPWORDS = []

# https://dle.rae.es/contenido/abreviaturas-y-signos-empleados
ABR_REG = {'Ál.': 'Álava', 'Alb.': 'Albacete', 'Alm.': 'Almería', 'Am.': 'América', 'Am. Cen.': 'América Central', 'Am. Mer.': 'América Meridional', 'And.': 'Andalucía', 'Ant.': 'Antillas', 'Ar.': 'Aragón', 'Arg.': 'Argentina', 'Ast.': 'Asturias', 'Áv.': 'Ávila', 'Bad.': 'Badajoz', 'Bal.': 'Islas Baleares', 'Bil.': 'Bilbao', 'Bol.': 'Bolivia', 'Burg.': 'Burgos', 'Các.': 'Cáceres', 'Cád.': 'Cádiz', 'Can.': 'Canarias', 'Cantb.': 'Cantabria', 'Cast.': 'Castilla', 'Cat.': 'Cataluña', 'Col.': 'Colombia', 'Córd.': 'Córdoba', 'C. Real': 'Ciudad Real', 'C. Rica': 'Costa Rica', 'Cuen.': 'Cuenca', 'Ec.': 'Ecuador', 'EE. UU.': 'Estados Unidos', 'El Salv.': 'El Salvador', 'Esp.': 'España', 'Ext.': 'Extremadura', 'Filip.': 'Filipinas', 'Gal.': 'Galicia', 'Gran.': 'Granada', 'Gran Can.': 'Gran Canaria', 'Guad.': 'Guadalajara', 'Guat.': 'Guatemala', 'Guin.': 'Guinea Ecuatorial', 'Guip.': 'Guipúzcoa', 'Hond.': 'Honduras', 'Huel.': 'Huelva', 'Hues.': 'Huesca', 'Mad.': 'Madrid', 'Mál.': 'Málaga', 'Man.': 'La Mancha', 'Méx.': 'México', 'Mur.': 'Murcia', 'Nav.': 'Navarra', 'Nic.': 'Nicaragua', 'Pal.': 'Palencia', 'Pan.': 'Panamá', 'Par.': 'Paraguay', 'P. Rico': 'Puerto Rico', 'P. Vasco': 'País Vasco', 'R. Dom.': 'República Dominicana', 'Sal.': 'Salamanca', 'Seg.': 'Segovia', 'Sev.': 'Sevilla', 'Sor.': 'Soria', 'Ter.': 'Teruel', 'Tol.': 'Toledo', 'Ur.': 'Uruguay', 'Val.': 'Valencia', 'Vall.': 'Valladolid', 'Ven.': 'Venezuela', 'Vizc.': 'Vizcaya', 'Zam.': 'Zamora', 'Zar.': 'Zaragoza'}
ABR_REG.update({'Chile': 'Chile', 'Cuba': 'Cuba', 'Perú': 'Perú'})

ABR_TEMA = {'Acús.': 'acústica', 'Aer.': 'aeronáutica', 'Agr.': 'agricultura', 'Alq.': 'alquimia', 'Anat.': 'anatomía', 'Antrop.': 'antropología', 'Arq.': 'arquitectura', 'Arqueol.': 'arqueología', 'Astron.': 'astronomía', 'Astrol.': 'astrología', 'Biol.': 'biología', 'Bioquím.': 'bioquímica', 'Bot.': 'botánica', 'Carp.': 'carpintería', 'Cineg.': 'cinegética', 'Cinem.': 'cinematografía', 'Com.': 'comercio', 'Constr.': 'construcción', 'Dep.': 'deportes', 'Der.': 'derecho', 'Ecd.': 'ecdótica', 'Ecol.': 'ecología', 'Econ.': 'economía', 'Electr.': 'electricidad; electrónica', 'Equit.': 'equitación', 'Esc.': 'escultura', 'Esgr.': 'esgrima', 'Estad.': 'estadística', 'Fil.': 'filosofía', 'Fís.': 'física', 'Fisiol.': 'fisiología', 'Fon.': 'fonética; fonología', 'Fórm.': 'fórmula', 'Fotogr.': 'fotografía', 'Geogr.': 'geografía', 'Geol.': 'geología', 'Geom.': 'geometría', 'Gram.': 'gramática', 'Heráld.': 'heráldica', 'Impr.': 'imprenta', 'Inform.': 'informática', 'Ingen.': 'ingeniería', 'Ling.': 'lingüística', 'Mar.': 'marina', 'Mat.': 'matemáticas', 'Mec.': 'mecánica', 'Med.': 'medicina', 'Meteor.': 'meteorología', 'Métr.': 'métrica', 'Mil.': 'milicia', 'Mit.': 'mitología', 'Mús.': 'música', 'Numism.': 'numismática', 'Ópt.': 'óptica', 'Ortogr.': 'ortografía', 'Parapsicol.': 'parapsicología', 'Pint.': 'pintura', 'Psicol.': 'psicología', 'Psiquiatr.': 'psiquiatría', 'Quím.': 'química', 'Rel.': 'religión', 'Ret.': 'retórica', 'Símb.': 'símbolo', 'Sociol.': 'sociología', 'Taurom.': 'tauromaquia', 'Tecnol.': 'tecnologías', 'Telec.': 'telecomunicación', 'T. lit.': 'teoría literaria', 'Topogr.': 'topografía', 'Transp.': 'transportes', 'TV.': 'televisión', 'Urb.': 'urbanismo', 'Veter.': 'veterinaria', 'Zool.': 'zoología'}

ABR_DESUS = {'ant.': 'anticuado; antiguo', 'desus.': 'desusado', 'p. us.': 'poco usado'}

ABREVIATURAS = {'a.': 'alto', 'abl.': 'ablativo', 'abrev.': 'abreviación', 'acep.': 'acepción', 'acort.': 'acortamiento', 'acrón.': 'acrónimo', 'act.': 'activo', 'acus.': 'acusativo', 'adapt.': 'adaptación; adaptado', 'adj.': 'adjetivo', 'adv.': 'adverbio; adverbial', 'advers.': 'adversativo', 'afect.': 'afectivo', 'afér.': 'aféresis', 'aim.': 'aimara', 'al.': 'alemán', 'alterac.': 'alteración', 'alus.': 'alusión', 'amer.': 'americano', 'antonom.': 'antonomasia', 'apl.': 'aplicado', 'apóc.': 'apócope', 'apos.': 'aposición', 'ár.': 'árabe', 'arag.': 'aragonés', 'art.': 'artículo', 'ast.': 'asturiano', 'atóm.': 'atómico', 'aum.': 'aumentativo', 'aux.': 'auxiliar; verbo auxiliar', 'b.': 'bajo', 'berb.': 'bereber', 'c.': 'como', 'cat.': 'catalán', 'celtolat.': 'celtolatino', 'cf.': 'confer', 'cient.': 'científico', 'clás.': 'clásico', 'coloq.': 'coloquial', 'comp.': 'comparativo', 'compos.': 'compositivo', 'conc.': 'concesivo', 'condic.': 'condicional', 'conj.': 'conjunción', 'conjug.': 'conjugación', 'conjunt.': 'conjuntivo', 'contracc.': 'contracción', 'copulat.': 'copulativo; verbo copulativo', 'cult.': 'culto', 'dat.': 'dativo', 'deformac.': 'deformación', 'dem.': 'demostrativo', 'der.': 'derivado', 'desc.': 'desconocido', 'despect.': 'despectivo', 'deter.': 'determinado', 'dialect.': 'dialectal', 'dim.': 'diminutivo', 'disc.': 'discutido', 'distrib.': 'distributivo', 'disyunt.': 'disyuntivo', 'elem.': 'elemento', 'escr.': 'escrito', 'esp.': 'español', 'estud.': 'estudiantil', 'etim.': 'etimología', 'eufem.': 'eufemismo; eufemístico', 'excl.': 'exclamativo', 'expr.': 'expresión; expresivo', 'ext.': 'extensión', 'f.': 'femenino; nombre femenino', 'fest.': 'festivo', 'fig.': 'figurado', 'fr.': 'francés', 'fr.': 'frase', 'frec.': 'frecuentativo', 'frec.': 'frecuentemente', 'fut.': 'futuro', 'gall.': 'gallego', 'gallegoport.': 'gallegoportugués', 'galolat.': 'galolatino', 'genit.': 'genitivo', 'ger.': 'gerundio', 'germ.': 'germanía', 'germ.': 'germánico', 'gót.': 'gótico', 'gr.': 'griego', 'guar.': 'guaraní', 'hebr.': 'hebreo', 'hisp.': 'hispánico', 'ilat.': 'ilativo', 'imit.': 'imitación; imitativo', 'imper.': 'imperativo', 'imperf.': 'imperfecto', 'impers.': 'impersonal; verbo impersonal', 'inc.': 'incierto', 'incoat.': 'incoativo', 'indef.': 'indefinido', 'indet.': 'indeterminado', 'indic.': 'indicativo', 'infant.': 'infantil', 'infinit.': 'infinitivo', 'infl.': 'influencia; influido; influjo', 'ingl.': 'inglés', 'intens.': 'intensivo', 'interj.': 'interjección; interjectivo', 'interrog.': 'interrogativo', 'intr.': 'intransitivo; verbo intransitivo', 'inus.': 'inusual', 'irl.': 'irlandés', 'irón.': 'irónico', 'irreg.': 'irregular', 'it.': 'italiano', 'jap.': 'japonés', 'jerg.': 'jerga; jergal', 'lat.': 'latín; latino', 'leng.': 'lenguaje', 'leon.': 'leonés', 'loc.': 'locución', 'm.': 'masculino; nombre masculino', '[u.] m.': '[usado] más', 'm. or.': 'mismo origen', 'malson.': 'malsonante', 'may.': 'mayúscula', 'metapl.': 'metaplasmo', 'metát.': 'metátesis', 'mod.': 'moderno', 'mozár.': 'mozárabe', 'n.': 'neutro', 'n. p.': 'nombre propio', 'neerl.': 'neerlandés', 'neg.': 'negación', 'negat.': 'negativo', 'nórd.': 'nórdico', 'núm.': 'número', 'occid.': 'occidental', 'occit.': 'occitano', 'onomat.': 'onomatopeya; onomatopéyico', 'or.': 'origen', 'orient.': 'oriental', 'part.': 'participio', 'pas.': 'pasivo', 'perf.': 'perfecto', 'pers.': 'persona', 'person.': 'personal', 'peyor.': 'peyorativo', 'pl.': 'plural', 'poét.': 'poético', 'ponder.': 'ponderativo', 'pop.': 'popular', 'port.': 'portugués', 'poses.': 'posesivo', 'pref.': 'prefijo', 'prep.': 'preposición', 'prepos.': 'preposicional', 'pres.': 'presente', 'pret.': 'pretérito', 'prnl.': 'pronominal; verbo pronominal', 'pron.': 'pronombre', 'pronom.': 'pronominal', 'prov.': 'provenzal', 'ref.': 'referido', 'refl.': 'reflexivo', 'reg.': 'regular', '[marca] reg.': '[marca] registrada', 'regres.': 'regresivo', 'relat.': 'relativo', 'rur.': 'rural', 's.': 'sustantivo', 'sánscr.': 'sánscrito', 'sent.': 'sentido', 'sínc.': 'síncopa', 'sing.': 'singular', 'subj.': 'subjuntivo', 'suf.': 'sufijo', 'sup.': 'superlativo', 'sust.': 'sustantivo', 't.': 'terminación', '[conj.] t.': '[conjunción] temporal', '[u.] t.': '[usado] también', 'Tb.': 'también', 'tr.': 'transitivo; verbo transitivo', 'trad.': 'traducción', 'u.': 'usado', 'V.': 'véase', 'var.': 'variante', 'verb.': 'verbal', 'vocat.': 'vocativo', 'vulg.': 'vulgar'}
