import streamlit as st
import datetime
from pymongo import MongoClient
import pandas as pd


# LOADS WAREHOUSE
# Initialize connection.
cluster = "mongodb+srv://Tomai:Hz3ry40lNFPeio0P@warehouse.konbq.mongodb.net/Warehouses?retryWrites=true&w=majority"
client = MongoClient(cluster)#(**st.secrets["mongo"]) cannot make secrets.toml work!
db = client.Warehouses
stocklist = db.wilm

#Website formatting
st.title("Wilmersdorf fridge stocks")
task1 = 'Cross check'
task2 = 'View backstocked refrigerated items'
task3 = 'Add/remove items'
task = st.sidebar.radio('Select operation',[task1, task2, task3])

#Cross check new items with backstock ones
if task == task1: 
    st.sidebar.markdown('### Upload excel file from new delivery')
    newitemsraw = st.sidebar.file_uploader("File will be cross-checked with backstock", type=["xls","xlsx"])
    #Once uploaded:
    if newitemsraw is not None:
        newitems = pd.read_excel(newitemsraw)['SKU'] #loads only SKU data
        matches = list(stocklist.find({'SKU': { '$in': list(newitems)}})) 
        if len(matches) == 0:
            st.info('All items must be taken to front.')
        else:
            st.info('The following items are present in backstock.') 
            st.markdown('---')
            number = 1
            for item in matches:
                st.markdown('{}. {}'.format(number, item["name"]))
                number += 1 #matches is a cursor
            st.markdown('---')
            st.info('Please put new items in fridge and bring old items to front.')

#View stocked items
if task == task2: 
    liststock = list(stocklist.find())
    for stockitem in liststock:
        if len(stockitem["batches"])>0:
            st.markdown("---\n{} ({})  -  **{:03}{}**\n -\n EAN: {}".format(stockitem["name"],stockitem["SKU"],stockitem["shelf"],stockitem["letter"],stockitem["EAN"]))
            for expdate in stockitem["batches"]:
                st.info(("{} items expire on {}\n".format(stockitem["batches"][expdate],expdate)))
    
#Scan items and modify their stock
if task == task3: 
    st.sidebar.markdown('### Scan item and press Enter')
    EAN = int('0'+st.sidebar.text_input('EAN (Select to scan)'))
    #Once scanned:
    if EAN != 0:
        #Find and print item
        stockitem = stocklist.find_one({'EAN': EAN})
        st.markdown('---')
        st.subheader("{} ({})  -  **{:03}{}**\n".format(stockitem["name"],stockitem["SKU"],stockitem["shelf"],stockitem["letter"]))
        st.text('')
        #Update form:
        form = st.form(key='updatestock')
        expdate = form.date_input('Enter expiration date')
        amount = form.number_input('Enter inventory change (positive or negative)',step=1,format='%i')
        submit = form.form_submit_button(label='Submit')
        
        #Save new warehouse
        if submit: #only excecutes on rerun
            expdate = expdate.strftime("%Y.%m.%d")
            try:
                stockitem['batches'][expdate] += amount
            except:
                stockitem['batches'][expdate] = amount
            if stockitem['batches'][expdate] <= 0:
                del stockitem['batches'][expdate]
            stocklist.update_one({'EAN':EAN},{'$set':{'batches':stockitem['batches']}})
            flag = False
            for expdate in stockitem["batches"]:
                st.info("{} items expire on {}\n".format(stockitem["batches"][expdate],expdate))
                flag = True
            if flag == False:
                st.info("No items in backstock")
        else: #if no update is sent, prints stock anyway
            flag = False
            for expdate in stockitem["batches"]:
                st.info("{} items expire on {}\n".format(stockitem["batches"][expdate],expdate))
                flag = True
            if flag == False:
                st.info("No items in backstock")