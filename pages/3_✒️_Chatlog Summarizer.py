import streamlit as st
import pandas as pd
import re
from google.oauth2 import service_account
from google.cloud import translate
import nltk
import json
from st_aggrid import GridOptionsBuilder, AgGrid, GridUpdateMode, DataReturnMode
import io
import datetime





# set page to wide by default
st.set_page_config(layout="wide", page_title="Chatlog Summarizer", page_icon="🔖")

@st.cache
def download_nltk_data():
    nltk.download('stopwords')
    nltk.download('vader_lexicon')

download_nltk = download_nltk_data()


# nltk dependencies
from nltk.sentiment import SentimentIntensityAnalyzer
from nltk.tokenize import RegexpTokenizer
from nltk.corpus import stopwords

# Create API client google cloud
credentials = service_account.Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=["https://www.googleapis.com/auth/cloud-platform"])
client = translate.TranslationServiceClient(credentials=credentials)
project_id = "teak-advice-354202"
parent = "projects/teak-advice-354202/locations/global"




st.title("Chatlog Summarizer")

upload_file =  st.file_uploader("Upload your Excel file", help="Please upload your file at first")


if upload_file is not None:
    file = pd.ExcelFile(upload_file)
    df = pd.concat([pd.read_excel(file, sheet_name=sheet) for sheet in file.sheet_names], axis=0)
    df.columns = df.columns.str.lower().str.replace(" ", "_")

    # create columns
    col_1, col_2 = st.columns(2)

    # column selection
    select_col1 = col_1.selectbox("Select phone column", options=df.columns.to_list(), help="Selecting phone number column as index")
    select_col2 = col_2.selectbox("Select message column", options=df.columns.to_list(), help="Selecting column containing messages to be analyzed")
    # initiate session_state
    if "phone_selected" not in st.session_state:
        st.session_state["phone_selected"] = select_col1

    if "message_selected" not in st.session_state:
        st.session_state["message_selected"] = select_col2


    submit_cols = st.button("Choose columns")

    if submit_cols:
        st.session_state["phone_selected"] = select_col1
        st.session_state["message_selected"] = select_col2

    st.write(f"You selected: {st.session_state}")
    
    @st.cache(allow_output_mutation=True)
    def get_main_data():

        df_selected = df.loc[:, [st.session_state["phone_selected"], st.session_state["message_selected"]]].copy()

        ############################### CLEANING PART 1 #######################

        # lower the message
        df_selected[select_col2] = df_selected[select_col2].astype("str").str.lower()

        # function to clean words
        def search_words(text):
            result = re.findall(r'\b[^\d\W]+\b', text)
            return " ".join(result)

        # apply function to message
        df_selected[select_col2] = df_selected[select_col2].apply(lambda x : search_words(x))

        # next step cleaning (remove underscores)
        df_selected[select_col2] = df_selected[select_col2].str.replace('_', '')

        ############################### GROUPBY THE SENTENCE #######################
        df_grouped = df_selected.groupby([select_col1], as_index = False).agg({select_col2: list})

        # unpack list using join
        df_grouped[select_col2] = df_grouped[select_col2].apply(" ".join)

        # counting length of sentences
        df_grouped["len_words"] = df_grouped[select_col2].str.split().str.len()

        ############################### CLEANING PART 2 (AFTER GROUPBY) #######################

        # create function to remove duplicates
        def remove_duplicate_words(string):
            x = string.split()
            x = sorted(set(x), key = x.index)
            return ' '.join(x)

        # apply remove duplicates
        df_grouped[select_col2] = df_grouped[select_col2].apply(lambda x : remove_duplicate_words(x))

        # removing zero values of length of sentences
        df_grouped = df_grouped.loc[df_grouped["len_words"] > 0].copy()

        ############################### TRANSLATIONS #######################
        # create function to translate text
        def translate_text(text):
            # Translate text from Indonesian to English
            # Detail on supported types can be found here:
            # https://cloud.google.com/translate/docs/supported-formats
            response = client.translate_text(
                request={
                    "parent": parent,
                    "contents": [text],
                    "mime_type": "text/plain",  # mime types: text/plain, text/html
                    "source_language_code": "id",
                    "target_language_code": "en-US",
                }
            )

            # Display the translation for each input text provided
            for translation in response.translations:
                result = translation.translated_text
                
            return result

        # apply translate text
        df_grouped["translated"] = df_grouped[select_col2].apply(lambda x: translate_text(x))

        ############################### NLTK PREPROCESSING #########################

        # Tokenization
        regexp = RegexpTokenizer('\w+') # words only
        df_grouped["translated_token"] = df_grouped["translated"].apply(regexp.tokenize)

        # Stopwords
        # Make a list of english stopwords
        stopwords = nltk.corpus.stopwords.words("english")

        # Extend the list with your own custom stopwords
        my_stopwords = ['https', 'http', 'co', 'com', 'id', 'media', 'message', 'bot', 'audio', 'text', 'video', 'document', 'image']
        stopwords.extend(my_stopwords)

        # remove stopwords
        df_grouped["translated_token"] = df_grouped["translated_token"].apply(lambda x: [item for item in x if item not in stopwords])
        df_grouped['translated_token'] = df_grouped['translated_token'].apply(lambda x: ' '.join([item for item in x]))
        # new column to count length of words
        df_grouped["len_word_translated"] = df_grouped["translated_token"].str.split().str.len()
        # filter only above 1 word
        df_grouped = df_grouped.loc[df_grouped["len_word_translated"] > 1].copy()

        # Sentiment Intensity Analyzer
        analyzer = SentimentIntensityAnalyzer()

        df_grouped['sia_polarity'] = df_grouped['translated_token'].apply(lambda x: analyzer.polarity_scores(x))

        ############################### EXPLODE SENTIMENT SCORE ###########################
        # normalize the column order_transaction
        json_polarity = json.loads(df_grouped[[select_col1, "sia_polarity"]].to_json(orient="records"))    
        df_polarity = pd.json_normalize(json_polarity)
        df_polarity['sentiment'] = df_polarity['sia_polarity.compound'].apply(lambda x: 'positive' if x >0 else 'neutral' if x==0 else 'negative')

        ############################### MERGE DATAFRAME ###########################
        dataframe = pd.merge(df_grouped, df_polarity, how="left", left_on=select_col1, right_on=select_col1) 
    
        return dataframe

    # run get_main_data
    df_merged = get_main_data()

    ############################### FILTER DATAFRAME ###########################
    # st cache
    @st.cache
    def get_filtered_data():

        dataframe = df_merged.loc[(df_merged["sia_polarity.compound"] <= 0.8) &
                                    (df_merged["len_word_translated"] < 30)].copy()
        
        dataframe = dataframe.loc[:, [select_col1, select_col2, "len_word_translated", "sia_polarity.neg", "sia_polarity.neu", "sia_polarity.pos", "sia_polarity.compound", "sentiment"]].copy()

        return dataframe

    # run get_filtered_data
    df_filtered = get_filtered_data()

    ############################### AG GRID DATAFRAME ###########################
    gb = GridOptionsBuilder.from_dataframe(df_filtered)


    update_mode_value = GridUpdateMode.SELECTION_CHANGED
    return_mode_value = DataReturnMode.FILTERED

    gb.configure_selection(selection_mode='multiple', use_checkbox=True, groupSelectsFiltered=True, groupSelectsChildren=True)
    gridOptions = gb.build()



    grid_response = AgGrid(
        df_filtered,
        gridOptions=gridOptions,
        update_mode=update_mode_value,
        return_mode=return_mode_value,
        theme='streamlit'
    )

    df_final = grid_response['data']
    selected = grid_response['selected_rows']
    selected_df = pd.DataFrame(selected)

    
    
    st.dataframe(selected_df)
    # download file
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        # Write excel with single worksheet
        selected_df.to_excel(writer, index=False)
        # Close the Pandas Excel writer and output the Excel file to the buffer
        writer.save()

        # assign file to download button
        st.download_button(
            label="Download Data in Excel",
            data=buffer,
            file_name=f"cleaned_chatlog_{datetime.datetime.now().strftime('%Y-%m-%d')}.xlsx",
            mime="application/vnd.ms-excel"
    )
    
else:
    st.warning("You must upload file first to use the tool.")