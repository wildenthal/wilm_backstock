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
task = st.sidebar.radio('Normal operations',[task1, task2, task3])

#Rerun counter
if 'count' not in st.session_state:
    st.session_state.count = 0
print('This is run {}.'.format(st.session_state.count))
st.session_state.count += 1

#Button to toggle advanced options
advanced = st.sidebar.button('Toggle advanced options')
#Session state to store whether advanced options are enabled
if 'advenabled' not in st.session_state:
	st.session_state.advenabled = False
#Resets advanced options when toggled twice and reruns to clear
if advanced == True and st.session_state.advenabled == True:
    st.session_state.advenabled = False
    st.experimental_rerun()


#Cross check new items with backstock ones
if task == task1 and st.session_state.advenabled == False: 
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
if task == task2 and st.session_state.advenabled == False: 
    liststock = list(stocklist.find())
    for stockitem in liststock:
        if len(stockitem["batches"])>0:
            st.markdown("---\n{} ({})  -  **{:03}{}**\n -\n EAN: {}".format(stockitem["name"],stockitem["SKU"],stockitem["shelf"],stockitem["letter"],stockitem["EAN"]))
            for expdate in stockitem["batches"]:
                st.info(("{} items expire on {}\n".format(stockitem["batches"][expdate],expdate)))
    
#Scan items and modify their stock
if task == task3 and st.session_state.advenabled == False: 
    st.sidebar.markdown('### Scan item and press Enter')
    EAN = int('0'+st.sidebar.text_input('EAN (Select to scan)'))
    #Once scanned:
    if EAN != 0:
        #Find and print item
        stockitem = stocklist.find_one({'EAN': EAN})
        st.markdown('---')
        try:
            st.subheader("{} ({})  -  **{:03}{}**\n".format(stockitem["name"],stockitem["SKU"],stockitem["shelf"],stockitem["letter"]))
            st.text('')
            #Update form:
            form = st.form(key='updatestock')
            expdate = form.date_input('Enter expiration date')
            amount = form.number_input('Enter inventory change (positive or negative)',step=1,format='%i')
            submit = form.form_submit_button(label='Submit')
            exists = True
        except TypeError:
            st.markdown('Item is not in database. Please add missing EAN or item through advanced options.')
            submit=False
            exists = False
        
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
        elif exists: #if no update is sent, prints stock anyway
            flag = False
            for expdate in stockitem["batches"]:
                st.info("{} items expire on {}\n".format(stockitem["batches"][expdate],expdate))
                flag = True
            if flag == False:
                st.info("No items in backstock")

if advanced == True:
    st.session_state.advenabled = True
    st.experimental_rerun()

if st.session_state.advenabled == True:
    task4 = 'Correct EAN/SKU/name/shelf'
    task5 = 'View all refrigerated items'
    task = st.sidebar.radio('Disable advanced options for normal operation',[task4,task5])
    if task == task4:
        option = st.sidebar.selectbox('Select field to correct',('Enter missing EANS','Add missing item','Edit existing item'))
        if option == 'Enter missing EANS':
            flag = False
            for shelfnumber in range(9,15):
                st.markdown('### Fridge {}:'.format(shelfnumber))
                stockshelf = stocklist.find({'EAN':0,'shelf':shelfnumber})
                for stockitem in stockshelf:
                    EAN = int('0'+st.text_input('Please enter EAN for {} on shelf {} with SKU {}'.format(stockitem['name'],stockitem['letter'],stockitem['SKU'])))
                    if EAN !=0:
                        stocklist.update_one({"_id" : stockitem["_id"] }, {"$set" : {"EAN" :EAN}})
                        st.markdown('Success!')
                    flag=True
            for shelfnumber in range(79,86):
                st.markdown('### Fridge {}:'.format(shelfnumber))
                stockshelf = stocklist.find({'EAN':1,'shelf':shelfnumber})
                for stockitem in stockshelf:
                    EAN = int('0'+st.text_input('Please enter EAN for {} on shelf {} with SKU {}'.format(stockitem['name'],stockitem['letter'],stockitem['SKU'])))
                    if EAN !=0:
                        if EAN == 137:
                            stocklist.delete_one({"_id" : stockitem["_id"] })
                            print(f'deleted item with id {stockitem["_id"]}')
                        else:
                            stocklist.update_one({"_id" : stockitem["_id"] }, {"$set" : {"EAN" :EAN}})
                        st.markdown('Success!')
                    flag=True
            if flag == False:
                st.markdown('### All items have EANS!')
        if option == 'Add missing item':
            EAN = int('0'+st.text_input('Please enter EAN and press Enter'))
            SKU = int('0'+st.text_input('Please enter SKU and press Enter'))
            name = ''+st.text_input('Please enter item name and press Enter')
            shelf = int('0'+st.text_input('Please enter fridge number (e.g. 9, 13, 79) and press Enter'))
            letter = ''+st.text_input('Please enter shelf (e.g. A, B, C) and press Enter')
            #if EAN != 0 and SKU != 0 and shelf != 0 and letter != '':
            st.markdown('Make sure everything is correct!')
            confirm = st.button('Click to confirm')
            if confirm:
                stocklist.insert_one({'EAN':EAN, 'SKU':SKU, 'name':name,'shelf':shelf,'letter':letter})
                st.info('Item has successfuly been added')
        if option == 'Edit existing item':
            st.sidebar.markdown('### Enter EAN or SKU')
            EAN = int('0'+st.sidebar.text_input('Enter EAN and press Enter'))
            SKU = int('0'+st.sidebar.text_input('Enter SKU and press Enter'))
            st.markdown('This is not yet finished. Will not work.')
            if EAN != 0:
                stockitem = stocklist.find_one({'EAN':EAN})
                try:
                    st.markdown("{} ({})  -  **{:03}{}**\n".format(stockitem["name"],stockitem["SKU"],stockitem["shelf"],stockitem["letter"]))
                    suboption = st.selectbox('Enter field to edit',('SKU','Name','Fridge number','Shelf letter'))
                    if suboption == 'SKU':
                        SKU = int('0'+st.text_input('Enter new SKU'))
                        send = st.button('Click to change')
                        if send:
                            st.markdown('Success!')
                    if suboption == 'Name':
                        name = ''+st.text_input('Enter new name')
                        send = st.button('Click to change')
                        if send:
                            st.markdown('Success!')
                    if suboption == 'Fridge number':
                        shelf = int('0'+st.text_input('Enter new fridge number'))
                        send = st.button('Click to change')
                        if send:
                            st.markdown('Success!')
                    if suboption == 'Shelf letter':
                        letter = ''+st.text_input('Enter new shelf letter')
                        send = st.button('Click to change')
                        if send:
                            st.markdown('Success!')
                except:
                    st.info("Item not found. Please add missing EAN or item.")
    if task == task5:
        load = st.button('Press to load')
        letterlist = ['A','B','C','D','E','F','G','H','I']
        if load:
            for shelf in range(9,15):
                st.markdown('### Fridge {}'.format(shelf))
                for letter in letterlist:
                    st.markdown('**Shelf {}**'.format(letter))
                    for stockitem in stocklist.find({'shelf':shelf,'letter':letter}):
                        st.markdown("{} ({})  -  EAN: {}\n".format(stockitem["name"],stockitem["SKU"],stockitem["EAN"]))
            for shelf in range(79,86):
                st.markdown('### Fridge {}'.format(shelf))
                for letter in letterlist:
                    st.markdown('**Shelf {}**'.format(letter))
                    for stockitem in stocklist.find({'shelf':shelf,'letter':letter}):
                        st.markdown("{} ({})  -  EAN: {}\n".format(stockitem["name"],stockitem["SKU"],stockitem["EAN"]))