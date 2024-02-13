import streamlit as st
import pandas as pd
import copy, random, time
import src.utils as utils

st.set_page_config(
    page_title="Denominador común",
    page_icon="🔤",
    layout="centered",
    menu_items={
        'Get help': "https://dirdam.github.io/contact.html",
        'About': """Este juego ha sido creado por [Adrián Jiménez Pascual](https://dirdam.github.io/)."""
    })

# TODO: mirar que pasa con las palabras como torero, ra

# Title
st.title("Denominador común")
st.write("Un juego de ingenio en el que has de adivinar qué concepto tienen en común las palabras que se te presentan. La palabra a adivinar ha de escribirse en su forma singular y, en caso de tener género, en masculino.")
st.write("Puedes **cambiar la dificultad** en cualquier momento y no se perderá tu progreso. ¡Intenta niveles más difíciles para ganar **más puntos**!")

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
    my_df = my_df[my_df['kinds'] == kind]
    return my_drae, my_df, df

with st.spinner("Leyendo el diccionario..."):
    my_drae, my_df, df = load_dicts()

### Game
if 'score' not in st.session_state:
    st.session_state.score = 0
    st.session_state.round = 1
# Select difficulty
def update_show_word():
    del st.session_state.show_word

difficulty_names = {'easy': 'Paisano (consigue hasta 15 puntos)', 'normal': 'Cosmopolita (consigue hasta 20 puntos)', 'hard': 'Explorador (consigue hasta 25 puntos)'}
difficulty_max_score = {'easy': 15, 'normal': 20, 'hard': 25}
difficulty = st.selectbox("Selecciona la dificultad:", list(difficulty_names.keys()), format_func=lambda x: difficulty_names[x], on_change=update_show_word) # On change generates a new word
target_commonness = {'easy': 4, 'normal': 3, 'hard': 2}
acep_limit = {'easy': 1, 'normal': 3, 'hard': None}
hint_types = {'easy': [4, 4, 3, 3, 4, 3], 'normal': [4, 3, 2, 2, 3, 2], 'hard': [3, 2, 1, 0, 3, 2]}

# Get new word
if 'show_word' not in st.session_state:
    st.session_state.hint2_checked = False
    st.session_state.hint3_checked = False
    st.session_state.temp_score = difficulty_max_score[difficulty]
    with st.spinner("Buscando palabra objetivo..."):
        show_solutions = False
        common_word = ''
        while not show_solutions: # Mientras no haya soluciones para las pistas requeridas sigue buscando
            common_word = utils.get_random_word(my_df, commonness=target_commonness[difficulty], appear_lim=len(hint_types[difficulty]))
            solutions = utils.words_with_word(my_drae, common_word) # Busco dentro de `my_drae` que es el diccionario restringido
            solutions = utils.limit_defs(solutions, limit_acep=acep_limit[difficulty]) # Limita a acepciones posibles
            solutions = utils.add_commonness(solutions, df) # Para añadir las rarezas uso `df` original, que incluye todas las palabras
            show_solutions = utils.pick_solutions(solutions, common_word, hints=hint_types[difficulty], avoid_common=True) # Comprueba que se puedan dar todas las pistas previstas y las recoge
    show_word = df[df['word'] == common_word]['simple_word'].iloc[0]
    st.session_state.show_word = show_word
    st.session_state.show_solutions = show_solutions
else:
    show_word = st.session_state.show_word
    show_solutions = st.session_state.show_solutions

st.markdown(f"### Ronda {st.session_state.round}")
st.markdown("#### Primera pista")
st.markdown(f"- Primera letra: **{show_word[0].upper()}**")
st.markdown('La pablabra aparece en la definición de:\n')
for i, (hint_word, hint_def, diff) in enumerate(show_solutions[:len(hint_types[difficulty]) - 2]):
    hint_def = utils.modify_def(show_word, hint_def)
    with st.expander(f"**{hint_word}**"):
        st.write(f"{hint_def}")
placeholder = show_word[0] + "_"
            
st.markdown("#### Segunda pista")
if st.checkbox("Mostrar segunda pista (_resta 5 puntos_)", value=st.session_state.hint2_checked, disabled=True if st.session_state.hint2_checked else False):
    if not st.session_state.hint2_checked: # If first time, disable checkbox, change score and rerun
        st.session_state.hint2_checked = True
        st.session_state.temp_score -= 5
        st.rerun()
    st.markdown(f"- Última letra: **{show_word[-1].upper()}**")
    st.markdown('También aparece en la definición de:\n')
    hint_word, hint_def, diff = show_solutions[len(hint_types[difficulty]) - 2]
    hint_def = utils.modify_def(show_word, hint_def)
    with st.expander(f"**{hint_word}**"):
        st.write(f"{hint_def}")
    placeholder = placeholder + show_word[-1]

st.markdown("#### Tercera pista")
if st.checkbox("Mostrar tercera pista (_resta 5 puntos_)", value=st.session_state.hint3_checked, disabled=True if not st.session_state.hint2_checked else (True if st.session_state.hint3_checked else False)):
    if not st.session_state.hint3_checked: # If first time, disable checkbox, change score and rerun
        st.session_state.hint3_checked = True
        st.session_state.temp_score -= 5
        st.rerun()
    st.markdown(f"- Longitud de la palabra: **{len(show_word)}** letras")
    st.markdown('También aparece en la definición de:\n')
    hint_word, hint_def, diff = show_solutions[len(hint_types[difficulty]) - 1]
    hint_def = utils.modify_def(show_word, hint_def)
    with st.expander(f"**{hint_word}**"):
        st.write(f"{hint_def}")
    placeholder = placeholder.replace('_', '_'*(len(show_word) - 2))

# Answer
round_finished = False
st.markdown("### Averigua la palabra")
answer = st.text_input(f"Por _**{st.session_state.temp_score} puntos**_, escribe la palabra que creas que está en la definición de todas las anteriores:", value="", placeholder=placeholder).lower()
if answer == show_word:
    st.success("¡Correcto!")
    st.session_state.score += st.session_state.temp_score
    round_finished = True
else:
    if answer:
        st.error("¡Incorrecto! Inténtalo de nuevo.")
        if st.button("Me rindo 😔"):
            st.warning(f"La palabra era: **{show_word}**")
            round_finished = True

# Score
cols = st.columns([1, 2, 1])
with cols[1]:
    st.markdown(f"### Puntuación: {st.session_state.score} puntos")
    score_bar = st.progress(min(st.session_state.score, 100)) # 100 is the maximum score
    # st.balloons()

# Generate new word
if round_finished: # If the round has finished, generate a new word
    for key in st.session_state.keys():
        if key not in ['score', 'round']: # Delete all keys except 'score' and 'round'
            del st.session_state[key]
    st.session_state.round += 1
    time.sleep(1)
    st.rerun()

# End of game
if st.session_state.score >= 100:
    st.session_state.round -= 1
    st.balloons()
    st.success(f"¡Felicidades! Has completado el juego en **{st.session_state.round}** rondas.")
    face_options = ['🙃', '🤔', '🙂', '😊']
    if st.button(f"¿Jugar otra partida? {random.choice(face_options)}"):
        st.session_state.score = 0
        st.session_state.round = 1
        st.rerun()