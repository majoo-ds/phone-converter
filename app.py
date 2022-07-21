import io
import streamlit as st
import pandas as pd
import datetime
from PIL import Image

# favicon image
im = Image.open("favicon.ico")

# set page to wide by default
st.set_page_config(page_title="Phone Number Converter", page_icon=im)

st.title("Phone Number Converter")
st.subheader("Please, review this guideline before uploading yout file.")
st.markdown("1. Make sure file has no skipping rows")
st.markdown("2. Format phone number column into __Number__")
st.markdown("3. It'd be better to have a single sheet in it")
st.markdown("4. If it has multiple sheets, make sure they're all in same structure.")

upload_file =  st.file_uploader("Upload your file")
st.warning("You must upload file first to quit the error message.")
file = pd.ExcelFile(upload_file)

if upload_file is not None:
    df = pd.concat([pd.read_excel(file, sheet_name=sheet) for sheet in file.sheet_names], axis=0)
else:
    st.warning("You must upload file first to quit the error message shown below.")


df.columns = df.columns.str.lower().str.replace(" ", "_")
st.warning("You must change column name to quit the error message shown below.")
select_col = st.selectbox("Select a column to be converted", options=df.columns.to_list())

# initiate session_state
if "column_selected" not in st.session_state:
    st.session_state["column_selected"] = select_col

submit_col = st.button("Change column")

if submit_col:
    st.session_state["column_selected"] = select_col

st.write(select_col)

df[select_col] = df[select_col].astype("str")
df[select_col] = df[select_col].str.replace("-","")
df[select_col] = df[select_col].str.replace("(","")
df[select_col] = df[select_col].str.replace(")","")
df[select_col] = df[select_col].str.replace(" ","")
df[select_col] = df[select_col].str.replace("+","")
df[select_col] = df[select_col].str.replace("*","")
df = df.loc[~df[select_col].str.contains(r'(\d)\1{5}')].copy()
df["len"] = df[select_col].str.len()

df = df.loc[((df[select_col].str.contains("^62")) | 
             (df[select_col].str.contains("^8")) | 
             (df[select_col].str.contains("^08")))].copy()

df = df.loc[df["len"] > 8].copy()

df["nomor_telepon_clean"] = df.apply(lambda row:
                          "62" + row[select_col][:] if row[select_col].startswith("8")
                           else row[select_col].replace("0", "62", 1) if row[select_col].startswith("0")
                           else row[select_col].replace(row[select_col][0:3], "62", 1) if row[select_col].startswith("620")
                        else row[select_col], axis=1)

df.drop_duplicates(subset="nomor_telepon_clean", inplace=True)

df["zero_num"] = df.apply(lambda row: 
                          row["nomor_telepon_clean"].replace(row["nomor_telepon_clean"][0:2], "0", 1) if row["nomor_telepon_clean"].startswith("62")
                          else row["nomor_telepon_clean"], axis=1)

# extract 4 first digits as prefix
df["prefix"] = df["zero_num"].str[0:4] 

# import provider prefix data
prefix_df = pd.read_csv("https://docs.google.com/spreadsheets/d/e/2PACX-1vT57RI1XkPG2OALUVDnRe4IuCc6RTrkIQ3MKlN-54pP-evs_Ku0BDtpcgmTujiTj0psdmJlbe5k-ibF/pub?output=csv")

# change data type
prefix_df["prefix"] = prefix_df["prefix"].astype("str")

# add zero into first character
prefix_df["prefix"] = "0" + prefix_df["prefix"].str[:]

# merge prefix_df and wappin_df
merge_df = pd.merge(df, prefix_df, how="left", left_on="prefix", right_on="prefix")

merge_df = merge_df.loc[merge_df["provider"].notnull()].copy()

st.markdown("__Cleaned File__")

st.dataframe(merge_df)

# downloadable dataframe button
buffer = io.BytesIO()
with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
    # Write excel with single worksheet
    merge_df.to_excel(writer, index=False)
    # Close the Pandas Excel writer and output the Excel file to the buffer
    writer.save()

    # assign file to download button
    st.download_button(
        label="Download Data in Excel",
        data=buffer,
        file_name=f"cleaned_phone_{datetime.datetime.now().strftime('%Y-%m-%d')}.xlsx",
        mime="application/vnd.ms-excel"
)