import streamlit as st
import datetime
import pandas as pd
from pymongo import MongoClient


# LOAD WAREHOUSE
# initialize connection
cluster = "mongodb+srv://Tomai:Hz3ry40lNFPeio0P@warehouse.konbq.mongodb.net/Warehouses?retryWrites=true&w=majority"
client = MongoClient(cluster)#(**st.secrets["mongo"]) cannot make secrets.toml work!
db = client.Warehouses
stocklist = db.wilm

#write page header
st.title("Wilmersdorf fridge stocks")

#create task chooser
task1 = 'Cross check'
task2 = 'View backstocked refrigerated items'
task3 = 'Add/remove items'

#create helper variable to edit items (task3) directly from backstock list (task2)
if 'helper' not in st.session_state:
    st.session_state.helper = {'bypass':False,'EAN':"","completed":True}
#bypass signals if task3 should be loaded
#EAN holds backstock item to be edited
#completed actually does nothing (see below)

#function to reset helper if editing is cancelled
def killhelper():
    st.session_state.helper = {'bypass':False,'EAN':"","completed":True} #not working as expected

#create task selector
task = st.sidebar.radio('Normal operations',[task1, task2, task3])#,on_change=killhelper())
if st.session_state.helper['bypass']:
    task = task3


#create rerun counter (logs to console for debugging)
if 'count' not in st.session_state:
    st.session_state.count = 0
print('This is run {}.'.format(st.session_state.count))
st.session_state.count += 1

#make button to toggle advanced options
advanced = st.sidebar.button('Toggle advanced options')
#create session state to store whether advanced options are enabled
if 'advenabled' not in st.session_state:
	st.session_state.advenabled = False
#reset advanced options when toggled twice and reruns to clear page
if advanced == True and st.session_state.advenabled == True:
    st.session_state.advenabled = False
    st.experimental_rerun()


#Cross check new items with backstock ones
if task == task1 and st.session_state.advenabled == False: 
    st.sidebar.markdown('### Upload excel file from new delivery')
    newitemsraw = st.sidebar.file_uploader("File will be cross-checked with backstock", type=["xls","xlsx"])
    #read uploaded file
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
    #load everything as a list
    liststock = list(stocklist.find())
    #create array of zeros to signal if a certain stocklist item should be edited
    edit = [0] * len(liststock)
    #enumerate only stocked items
    for idx,stockitem in enumerate(liststock):
        if len(stockitem["batches"])>0:
            st.markdown("---\n{} ({})  -  **{:03}{}**\n -\n EAN: {}".format(stockitem["name"],stockitem["SKU"],stockitem["shelf"],stockitem["letter"],stockitem["EAN"]))
            for expdate in stockitem["batches"]:
                st.info(("{} items expire on {}\n".format(stockitem["batches"][expdate],expdate)))
            #this button enables us to jump to task3
            edit[idx] = st.button(f'Click to edit item {stockitem["SKU"]}')
            if edit[idx]:
                task = task3
                #note: radio is not affected!! so we need session_state.helper bypass to stay in task3 until we are finished. maybe there is a better way?
                st.session_state.helper["bypass"] = True
                #save EAN to be changed.
                st.session_state.helper["EAN"] = stockitem["EAN"]
                #again, useless (see even further below)
                st.session_state.helper["completed"]=False
                #now break so we get the task3 dialog immediately after this item
                break
                #note that if task3 block is moved above task2 block, code will be broken
    
#Scan items and modify their stock
if task == task3 and st.session_state.advenabled == False: 
    st.sidebar.markdown('### Scan item and press Enter')
    #set default EAN to preselected EAN from task2, or empty string if this was not done
    EAN = int('0'+st.sidebar.text_input('EAN (Select to scan)',st.session_state.helper["EAN"]))
    #Once EAN is present, load editor
    if EAN != 0:
        #find item in stocklist
        stockitem = stocklist.find_one({'EAN': EAN})
        st.markdown('---')
        #try to access item attributes
        try:
            st.subheader("{} ({})  -  **{:03}{}**\n".format(stockitem["name"],stockitem["SKU"],stockitem["shelf"],stockitem["letter"]))
            st.text('')
            #create update form
            form = st.form(key='updatestock')
            expdate = form.date_input('Enter expiration date')
            amount = form.number_input('Enter inventory change (positive or negative)',step=1,format='%i')
            submit = form.form_submit_button(label='Submit')
            #signal item exists
            exists = True
        #item will be None if EAN is invalid, so accessing attributes will give TypeError
        except TypeError:
            st.markdown('Item is not in database. Please add missing EAN or item through advanced options.')
            submit=False
            exists = False
        #Save new warehouse
        if submit: #only excecutes on rerun
            st.session_state.helper["bypass"] = False #clears bypass if it was selected
            st.session_state.helper["EAN"] = "" #clears EAN if it was specified
            expdate = expdate.strftime("%Y.%m.%d")
            #attempt to increase amount
            try:
                stockitem['batches'][expdate] += amount
            #if no amount exists for this date, catch exception and create amount
            except:
                stockitem['batches'][expdate] = amount
            #if amount is negative, delete!
            if stockitem['batches'][expdate] <= 0:
                del stockitem['batches'][expdate]
                
            stocklist.update_one({'EAN':EAN},{'$set':{'batches':stockitem['batches']}})
            
            #flag whether item is present in backstock
            flag = False
            for expdate in stockitem["batches"]:
                st.info("{} items expire on {}\n".format(stockitem["batches"][expdate],expdate))
                flag = True
            if flag == False:
                st.info("No items in backstock")
                
            #finally, the useless button: completed will always be set to True when this part is reached
            if st.session_state.helper["completed"] == False:
                st.session_state.helper["completed"]= not(st.button("Click to save changes"))
                
            #the reason this is added is to encourage the user to refresh the page when task3 is accessed from task2
            #button is not necessary to save changes: it exists only to avoid unexpected behavior.
            #if the user attempts to make another modification, they will trigger a rerun, and since bypass is false,
            #the page will go back to task2 without any indication of success. 
            #this tries to force the user to make only one edit at a time. it is an ugly solution.
            
        #if submit button is not pressed, show current stock
        elif exists and not(st.session_state.helper["bypass"]):
            flag = False
            for expdate in stockitem["batches"]:
                st.info("{} items expire on {}\n".format(stockitem["batches"][expdate],expdate))
                flag = True
            if flag == False:
                st.info("No items in backstock")

if advanced == True:
    st.session_state.advenabled = True
    #rerun to load advanced controls
    st.experimental_rerun()

if st.session_state.advenabled == True:
    task4 = 'Correct EAN/SKU/name/shelf'
    task5 = 'View all refrigerated items'
    #choose task and also alert user that normal operations are not active
    task = st.sidebar.radio('Disable advanced options for normal operation',[task4,task5])
    
    if task == task4:
        option = st.sidebar.selectbox('Select field to correct',('Enter missing EANS','Add missing item','Edit existing item'))
        if option == 'Enter missing EANS':
            #flag whether items are missing EANs
            flag = False
            
            #go over front fridges with null EAN == 0
            for shelfnumber in range(9,15):
                st.markdown('### Fridge {}:'.format(shelfnumber))
                stockshelf = stocklist.find({'EAN':0,'shelf':shelfnumber})
                for stockitem in stockshelf:
                    EAN = int('0'+st.text_input('Please enter EAN for {} on shelf {} with SKU {}'.format(stockitem['name'],stockitem['letter'],stockitem['SKU'])))
                    if EAN !=0:
                        stocklist.update_one({"_id" : stockitem["_id"] }, {"$set" : {"EAN" :EAN}})
                        st.markdown('Success!')
                    flag=True
            
            #go over back fridges with null EAN == 1
            for shelfnumber in range(79,86):
                st.markdown('### Fridge {}:'.format(shelfnumber))
                stockshelf = stocklist.find({'EAN':1,'shelf':shelfnumber})
                for stockitem in stockshelf:
                    EAN = int('0'+st.text_input('Please enter EAN for {} on shelf {} with SKU {}'.format(stockitem['name'],stockitem['letter'],stockitem['SKU'])))
                    if EAN !=0:
                        stocklist.update_one({"_id" : stockitem["_id"] }, {"$set" : {"EAN" :EAN}})
                        st.markdown('Success!')
                    flag=True
                    
            if flag == False:
                st.markdown('### All items have EANS!')
                
        if option == 'Add missing item':
            try:
                EAN = int('0'+st.text_input('Please enter EAN'))
                SKU = int('0'+st.text_input('Please enter SKU'))
                name = ''+st.text_input('Please enter item name')
                shelf = int('0'+st.text_input('Please enter fridge number (e.g. 9, 13, 79)'))
                letter = ''+st.text_input('Please enter shelf (e.g. A, B, C)')
                
                if letter not in ['','A','B','C','D','E','F','G','H','I']:
                    raise ValueError
                
                st.markdown('Make sure everything is correct!')
                confirm = st.button('Click to confirm')
                
                if confirm:
                    stocklist.insert_one({'EAN':EAN, 'SKU':SKU, 'name':name,'shelf':shelf,'letter':letter,'batches':dict()})
                    st.info('Item has successfuly been added')
            except ValueError:
                st.markdown("Please enter a valid value.")
        
        if option == 'Edit existing item': #to be finished
            st.sidebar.markdown('### Enter EAN or SKU')
            EAN = int('0'+st.sidebar.text_input('Enter EAN and press Enter'))
            SKU = int('0'+st.sidebar.text_input('Enter SKU and press Enter'))
            st.markdown('This is not yet finished. Will not do anything.')
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
                    
    if task == task5: #shows all refrigerated items
        letterlist = ['A','B','C','D','E','F','G','H','I']
        
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