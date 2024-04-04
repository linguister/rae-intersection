import streamlit as st
import pandas as pd
import copy, random, time
import src.utils as utils

st.set_page_config(
    page_title="Denominador común",
    page_icon="🔤",
    layout="centered",
    initial_sidebar_state="collapsed",
    menu_items={
        'Get help': "https://dirdam.github.io/contact.html",
        'About': """Este juego ha sido ideado y programado por [Adrián Jiménez Pascual](https://dirdam.github.io/)."""
    })

# Session states
# score: total score
# temp_score: score of the current round
# round: current round
# round_finished: if the round has finished
# show_word, show_solutions: word and solutions of the current round
# hint2_checked, hint3_checked: if the hints have been checked
# game_ended: if the game has ended

# Title
st.title("Denominador común")
st.write("Abre la pestaña de arriba a la izquierda (`>`) si necesitas leer las instrucciones.")

with st.sidebar:
    st.markdown("# Explicación")
    st.write("""
        - _**Denominador común**_ es un juego de ingenio en el que has de adivinar **qué palabra tienen en común** las definiciones de las palabras que se te presentan. 
            - Puede que cada definición use un significado distinto de la palabra objetivo (_polisemia_).
        - La palabra a adivinar siempre es un **sustantivo** y ha de escribirse en su forma _singular_ y, en caso de tener género, en _masculino_. (Es decir, como aparecería en el diccionario).
        - La **dificultad** sólo se puede eligir al principio de cada partida. Dificultades más altas se recompensan con **más puntos**.
            - Para cambiar de dificultad a mitad de partida carga de nuevo la página. Tu progreso se perderá.""")

# Load dictionaries
@st.cache_data(show_spinner=False) # Cache data so it doesn't have to be loaded every time
def load_dicts():
    drae = utils.load_dict('data/diccionario.json')
    df = pd.read_csv('data/diccionario_df.csv')
    my_drae = copy.deepcopy(drae)
    my_df = df.copy()    

    ### Operate with the dictionary
    # Remove all words that can have varios `kinds`
    my_df = utils.leave_single_kind(my_df)
    ########################## "muestra", "habla"??????????

    # Remove extremely common words (they are like wildcard words)
    # my_df = my_df[my_df['commonness'] != 4]
    # Remove extremely uncommon words (they are unknown)
    my_df = my_df[my_df['commonness'] != 0]

    # Remove regional and other words
    excl_group = dict()
    excl_group.update(utils.ABR_REG) # Quitar regionalismos
    excl_group.update(utils.ABR_TEMA) # Quitar temas
    excl_group.update(utils.ABR_DESUS) # Quitar desusadas
    my_drae = utils.exclude_group(my_drae, excl_group)

    ### Apply decisions and work with df
    # Restrict the df to the words in the dictionary
    my_df = my_df[my_df['word'].isin(my_drae.keys())]

    # Restrict the kind of words
    kind = 'sust' # 'sust', 'verb', 'adj', 'adv', 'prep', 'art', 'pron', 'interj', 'conj', 'onomat', 'elem', 'expr'
    my_df = my_df[my_df['kinds'] == kind] # TODO: 'la' me ha salido como palabra (y 'pesar')
    return my_drae, my_df, df

with st.spinner("Leyendo el diccionario..."):
    my_drae, my_df, df = load_dicts()

### Game
if 'score' not in st.session_state:
    st.session_state.score = 0
    st.session_state.round = 0
    st.session_state.difficulty = None
    st.session_state.game_ended = False
# Select difficulty
def update_show_word():
    if 'show_word' in st.session_state:
        del st.session_state.show_word

difficulty_max_score = {'easy': 15, 'normal': 20, 'hard': 25, 'extreme': 35, 'impossible': 50}
difficulty_names = {'easy': 'Aldeano', 'normal': 'Paisano', 'hard': 'Cosmopolita', 'extreme': 'Explorador', 'impossible': 'Kamikaze'}
difficulty_desc = {'easy': f"{difficulty_names['easy']} (rondas de {difficulty_max_score['easy']} puntos)", 
                    'normal': f"{difficulty_names['normal']} (rondas de {difficulty_max_score['normal']} puntos)", 
                    'hard': f"{difficulty_names['hard']} (rondas de {difficulty_max_score['hard']} puntos)", 
                    'extreme': f"{difficulty_names['extreme']} (rondas de {difficulty_max_score['extreme']} puntos)",
                    'impossible': f"{difficulty_names['impossible']} (rondas de {difficulty_max_score['impossible']} puntos)"}
target_commonness = {'easy': 4, 'normal': 3, 'hard': 2, 'extreme': 2, 'impossible': 1}
acep_limit = {'easy': 1, 'normal': 1, 'hard': 3, 'extreme': 5, 'impossible': None} # Límite de acepciones de la palabra objetivo (cuantas menos acepciones tenga menos variables sus usos)
hint_types = {'easy': [4, 4, 3, 4], 'normal': [4, 4, 3, 4], 'hard': [4, 3, 2, 3], 'extreme': [2, 2, 1, 0, 3], 'impossible': [2, 1, 1, 0, 3]}
if not st.session_state.difficulty:
    difficulty = st.selectbox("Selecciona la dificultad:", list(difficulty_desc.keys()), index=None, format_func=lambda x: difficulty_desc[x], on_change=update_show_word) # On change generates a new word
    if difficulty: # When chosen, set as difficulty for the rest of the game
        st.session_state.difficulty = difficulty
        st.rerun()
    else:
        st.stop() # Wait until difficulty selected
else:
    difficulty = st.session_state.difficulty
    st.markdown(f"Estás jugando en dificultad: **{difficulty_names[difficulty]}**.")

# Get new word
if 'show_word' not in st.session_state and not st.session_state.game_ended:
    st.session_state.hint2_checked = False
    st.session_state.hint3_checked = False
    st.session_state.temp_score = difficulty_max_score[difficulty]
    with st.spinner("Buscando palabra objetivo..."):
        show_solutions = False
        common_word = ''
        while not show_solutions: # Mientras no haya soluciones para las pistas requeridas sigue buscando
            common_word = utils.get_random_word(my_df, commonness=target_commonness[difficulty], appear_lim=len(hint_types[difficulty]))
            solutions = utils.words_with_word(my_drae, common_word) # Busco dentro de `my_drae` que es el diccionario restringido
            solutions = utils.limit_defs(solutions, limit_acep=acep_limit[difficulty]) # Limita el número de acepciones que la palabra objetivo tiene (cuantas menos acepciones menos lioso)
            solutions = utils.add_commonness(solutions, df) # Para añadir las rarezas uso `df` original, que incluye todas las palabras
            show_solutions = utils.pick_solutions(solutions, common_word, hints=hint_types[difficulty], avoid_common=True) # Comprueba que se puedan dar todas las pistas previstas y las recoge
    show_word = df[df['word'] == common_word]['simple_word'].iloc[0]
    st.session_state.show_word = show_word
    st.session_state.show_solutions = show_solutions
    st.session_state.round_finished = False # Initialize round_finished
    st.session_state.round += 1
    st.session_state.conceded = False
    print(show_word)
    shuffled_letters = [l.upper() for l in show_word[1:-1]]
    random.shuffle(shuffled_letters)
    st.session_state.shuffled_letters = ' '.join([show_word[0].upper()] + shuffled_letters + [show_word[-1].upper()])

st.markdown(f"### Ronda {st.session_state.round}")
st.markdown("#### Primera pista")
st.markdown(f"- Primera letra: **{st.session_state.show_word[0].upper()}**{' _'*(len(st.session_state.show_word) - 1)}")
st.markdown('La palabra aparece en la definición de:\n')
for i, (hint_word, hint_def, diff) in enumerate(st.session_state.show_solutions[:len(hint_types[difficulty]) - 1]):
    hint_def = utils.modify_def(st.session_state.show_word, hint_def)
    with st.expander(f"**{hint_word}**"):
        st.write(f"{hint_def}")
placeholder = st.session_state.show_word[0].upper() + ' _'*(len(st.session_state.show_word) - 1) # First letter and length
            
st.markdown("#### Segunda pista")
losing_points = difficulty_max_score[difficulty]//3
if st.checkbox(f"Mostrar segunda pista (_resta **{losing_points}** puntos_)", value=st.session_state.hint2_checked, disabled=True if st.session_state.hint2_checked else False):
    if not st.session_state.hint2_checked: # If first time, disable checkbox, change score and rerun
        st.session_state.hint2_checked = True
        st.session_state.temp_score -= losing_points
        st.rerun()
    st.markdown(f"- Última letra: {placeholder[:-1]}**{st.session_state.show_word[-1].upper()}**")
    st.markdown('También aparece en la definición de:\n')
    hint_word, hint_def, diff = st.session_state.show_solutions[len(hint_types[difficulty]) - 1]
    hint_def = utils.modify_def(st.session_state.show_word, hint_def)
    with st.expander(f"**{hint_word}**"):
        st.write(f"{hint_def}")
    placeholder = placeholder[:-1] + st.session_state.show_word[-1].upper() # Last letter

st.markdown("#### Tercera pista")
losing_points = difficulty_max_score[difficulty]//2 - difficulty_max_score[difficulty]//3
if st.checkbox(f"Mostrar tercera pista (_resta **{losing_points}** puntos_)", value=st.session_state.hint3_checked, disabled=True if not st.session_state.hint2_checked else (True if st.session_state.hint3_checked else False)):
    if not st.session_state.hint3_checked: # If first time, disable checkbox, change score and rerun
        st.session_state.hint3_checked = True
        st.session_state.temp_score -= losing_points
        st.rerun()
    st.markdown(f"- Anagrama de la palabra: **{st.session_state.shuffled_letters[0]}** {st.session_state.shuffled_letters[1:-1]} **{st.session_state.shuffled_letters[-1]}**")
    # st.markdown('También aparece en la definición de:\n')
    # hint_word, hint_def, diff = st.session_state.show_solutions[len(hint_types[difficulty]) - 1]
    # hint_def = utils.modify_def(st.session_state.show_word, hint_def)
    # with st.expander(f"**{hint_word}**"):
    #     st.write(f"{hint_def}")
    placeholder = placeholder + '    [ anagrama de:  ' + st.session_state.shuffled_letters + ' ]'

# Answer
st.markdown("### Averigua la palabra")
st.markdown(f"Jugando por: **{st.session_state.temp_score}** puntos.")
answer = st.text_input(f"Escribe la palabra que creas que está en la definición de todas las anteriores:", value="", placeholder=placeholder).lower()
answer = answer.replace(' ', '') # Remove spaces
st.button("Probar", use_container_width=True, type='primary')

if answer == st.session_state.show_word:
    st.success("¡Correcto!")
    st.session_state.score += st.session_state.temp_score
    st.session_state.round_finished = True
else:
    if not st.session_state.conceded:
        if answer:
            st.error("¡Incorrecto! Inténtalo de nuevo.")
            if st.button("Me rindo 😔", use_container_width=True):
                st.session_state.conceded = True
                st.rerun()
    else:
        st.warning(f"La palabra era: **{st.session_state.show_word}**")
        st.session_state.round_finished = True

# New round / Generate new word
if st.session_state.round_finished: # If the round has finished
    del st.session_state['show_word'] # Delete the word so a new one is generated
    if st.session_state.score < 100: # If not end of game, start a new round / generate a new word
        st.button('Siguiente palabra', use_container_width=True) # Just clicking means rerun
    else:
        st.session_state.game_ended = True

# Score
cols = st.columns([1, 2, 1])
with cols[1]:
    st.markdown(f"### Puntuación: {st.session_state.score}/100")
    score_bar = st.progress(min(st.session_state.score, 100)) # 100 is the maximum score

if st.session_state.game_ended: # If game ended
    time.sleep(0.5)
    st.balloons()
    st.success(f"¡Felicidades! Has completado el juego en **{st.session_state.round}** rondas.")
    del st.session_state.score
    del st.session_state.game_ended
    face = random.choice(['🙃', '🤔', '🙂', '😊'])
    st.button(f"¿Jugar otra partida? {face}", use_container_width=True) # Just clicking means rerun