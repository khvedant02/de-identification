import tarfile
from zipfile import ZipFile
import os
import xml.etree.ElementTree as ET
import pandas as pd
import numpy as np
from nltk.tokenize import word_tokenize, sent_tokenize
from keras.preprocessing.sequence import pad_sequences
import json

class PreProcessor:
    def __init__(self,title):
        self.words_seen = set()
        self.tags_seen = set()
        self.files_seen = [] #keeps track of doc id's
        
        self.max_len = 0
        self.title = title #title of folder to save data to

    def extract_file(self,file_path:str):
        """
        Extracts notes from compressed files. Only used once. 
        """
        if (file_path.endswith('.tar.gz') or file_path.endswith('.tgz')):
            try:
                tar = tarfile.open(file_path)
                tar.extractall()
                tar.close()
            except:
                print("Error in extracting tar file")
        elif (file_path.endswith('.zip')):
            try:
                with ZipFile(file_path,'r') as zipObj:
                    zipObj.extractall()
            except:
                print("Error in extracting zip file")

    def create_vocab_dict(self):
        """
        Creates word2idx dictionary: word -> index
        Create idx2word dictionary: index -> word
        """
        self.word2idx = {word: index + 2 for index,word in enumerate(self.words_seen)}
        self.word2idx["UNK"] = 1 # Unknown words
        self.word2idx["PAD"] = 0 # Padding

        self.idx2word = {index: word for word,index in self.word2idx.items()}

        self.vocab_size = len(self.word2idx.keys()) 

    def create_label_dict(self):
        """
        Creates tag2idx dictionary: BIO label -> index
        Create idx2tag dictionary: index -> BIO label
        """
        self.tag2idx = {tag: index + 2 for index,tag in enumerate(self.tags_seen)}
        self.tag2idx["O"] = 1 # non-PHI
        self.tag2idx["PAD"] = 0 # PAD

        self.idx2tag = {index: tag for tag,index in self.tag2idx.items()}

        self.tag_size = len(self.tag2idx.keys())

    def get_characters(self,note,tokens):
        """
        Gets the character range of each token.
        Params:
        note: raw string 
        tokens: sentences x tokens
        Returns:
        characters: sentences x tokens
        """
        current_token = ""
        characters = [] # list of tuples (start,end) of each token
        pointer = 0
        for i in range(len(tokens)): #sentences
            sentence_chars = []
            for j in range(len(tokens[i])): #tokens
                current_token = tokens[i][j]
                window_size = len(current_token)
                while True:
                    note_window = note[pointer:pointer+window_size]
                    if note_window == current_token:
                        #print("matched! ",current_token, " range: (",pointer,",",pointer+window_size,")")
                        sentence_chars.append((pointer,pointer+window_size))
                        pointer += 1
                        break
                    pointer += 1
            characters.append(sentence_chars)
        return characters

    def process_text(self,root,toPrint = 1):
        """
        Processes the actual note. Tokenizes, adds to vocab, returns (1xsentences),(1xsentencesxtokens)
        """
        #TODO: some text has dashes that are not tokenized. but the labels don't have those dashes.
        text_element = root.find('TEXT') # finds element with TEXT tag (i.e. the note)
        note: str = text_element.text
        note_sentences = sent_tokenize(note) # sentences
        note_tokens = list(map(lambda x: word_tokenize(x),note_sentences)) # sentences x tokens
        note_characters = self.get_characters(note,note_tokens) # sentences x tokens
        if toPrint == 0:
            self.get_characters(note,note_tokens)
        max_len = max(len(sent) for sent in note_tokens)
        if max_len > self.max_len:
            self.max_len = max_len
        self.words_seen.update([token for sent in note_tokens for token in sent]) # add tokens to vocab set
        return note_sentences, note_tokens, note_characters

    def process_tags(self,root,note_tokens):
        """
        Processes tags for a document. Uses BIO system presented in Deep Learning paper.
        """
        labels = []
        tag_element = root.find('TAGS')
        tag_queue = [] # (token, tag)
        for tag in tag_element:
            attributes = tag.attrib
            label_tokens = word_tokenize(attributes['text'])
            for i, token in enumerate(label_tokens): # seperate tags into tokens for B,I purposes
                if i == 0:
                    literal_tag ='B-'+attributes['TYPE']
                else:
                    literal_tag ='I-'+attributes['TYPE']
                tag_queue.append((token,literal_tag))
                self.tags_seen.add(literal_tag)

        next_token, next_tag = tag_queue.pop(0) # next_token is next token to have PHI
        for sentence in note_tokens:
            label_sentence = []
            for token in sentence:
                if next_token != token:
                    label_sentence.append('O')
                else:
                    label_sentence.append(next_tag)
                    if len(tag_queue) > 0:
                        next_token, next_tag = tag_queue.pop(0)  
            labels.append(label_sentence)

        return labels

    def process_data(self,data_sets, is_train_set: bool = True):
        """
        Creates sentence and token vectors for all the files in a folder.
        """
        print("Preprocessing data...")
        s_array = [] # documents x sentences
        t_array = [] # documents x sentences x tokens
        c_array = [] # documents x sentences x tokens
        labels = [] # documents x sentences x tokens
        i = 0
        for dir_name in data_sets:
            for filename in os.listdir(dir_name):
                self.files_seen.append(filename)
                tree = ET.parse(dir_name + filename) # must pass entire path
                root = tree.getroot()
                note_sentences, note_tokens, note_characters = self.process_text(root,i)
                s_array.append(note_sentences)
                t_array.append(note_tokens)
                c_array.append(note_characters)
                if is_train_set:
                    labels.append(self.process_tags(root,note_tokens))
                i+=1
    
        return s_array, t_array,c_array, labels

    def convert_to_df(self,t_array,c_array,labels):
        """
        Converts data to pandas df. df contains docid, unpadded sentences, and unpadded tags.
        """
        data = []
        for i in range(len(t_array)): # documents
            docid = self.files_seen.pop(0)[:-4] # strips .xml from doc id 
            for j in range(len(t_array[i])): # sentences
                tokenized_sentence = t_array[i][j]
                character_sentence = c_array[i][j]
                label_sentence = labels[i][j]
                id_tokens = list(map(lambda token: self.word2idx[token],tokenized_sentence))
                id_labels = list(map(lambda label: self.tag2idx[label],label_sentence))
                data.append({'docid':docid,'sentence':tokenized_sentence,
                'sentence_ids':id_tokens,'labels':label_sentence,'labels_ids':id_labels,
                'characters':character_sentence})
        df = pd.DataFrame(data)
        return df

    def unstring_ids(self,dictionary):
        return {int(k):v for k,v in dictionary.items()}

    def unstring_df_series(self,ids):
        """
        Unstrings a df series. Needed when you load data.
        """
        temp = []
        for sentence in ids:
            temp.append(eval(sentence))
        return temp

    def create_train_set(self,df,loading=False):
        """
        Creates training set using df by padding sequences and returning X,y. If loading, sentences are already padded.
        """
        if not loading: # NOT loading
            # pad id'd sentences and tags
            sentence_ids = df["sentence_ids"].copy()
            if type(sentence_ids[0]) is str:
                sentence_ids = self.unstring_df_series(sentence_ids)
            X = pad_sequences(maxlen=None, sequences=sentence_ids, dtype = 'int32', padding="post", value=self.word2idx["PAD"])
            df["padded_sentence"] = X.tolist()

            label_ids = df["labels_ids"].copy()
            if type(label_ids[0]) is str:
                label_ids = self.unstring_df_series(label_ids)
            y = pad_sequences(maxlen=None, sequences=label_ids, padding="post", value=self.tag2idx["PAD"])
            df["padded_labels"] = y.tolist()

        else: # loading
            X = df["padded_sentence"].copy()
            if type(X[0]) is str: # lists converted to strings when you save. must "unpack" string
                X = np.array(self.unstring_df_series(X))
            y = df["padded_labels"].copy()
            if type(y[0]) is str:
                y = np.array(self.unstring_df_series(y))

            self.max_len = y.shape[1]

        print("Shape of X: ", X.shape)
        print("Shape of y: ", y.shape)

        return X, y

    def save_processed_data(self,df):
        """
        Saves df to csv/excel and dictionaries to json
        """
        title = self.title
        folder = title + "/"
        path = folder + title
        if not os.path.exists(folder):
            os.makedirs(folder)
        if os.path.exists(path+'.xlsx'):
            os.remove(path+'.xlsx')
        df.to_excel(path+'.xlsx', sheet_name='PHI '+title)
        df.to_csv(path+'.csv')
        with open(path+'_word2idx.json','w') as f:
            json.dump(self.word2idx,f)
        with open(path+'_tag2idx.json','w') as f:
            json.dump(self.tag2idx,f)
        with open(path+'_idx2word.json','w') as f:
            json.dump(self.idx2word,f)
        with open(path+'_idx2tag.json','w') as f:
            json.dump(self.idx2tag,f)

    def load_processed_data(self,dir_name):
        """
        Directory contains csv file and dictionaries as json
        """
        print("Loading preprocessed data...")
        df = None
        if not dir_name.endswith('/'):
            dir_name = dir_name + "/"
        for filename in os.listdir(dir_name):
            path = dir_name + filename
            if filename.endswith('.csv'):
                df = pd.read_csv(path)
            if filename.endswith('word2idx.json'):
                with open(path) as f:
                    self.word2idx = json.load(f)
                    self.vocab_size = len(self.word2idx.keys()) 
            if filename.endswith('tag2idx.json'):
                with open(path) as f:
                    self.tag2idx = json.load(f)
                    self.tag_size = len(self.tag2idx.keys())
            if filename.endswith('idx2word.json'):
                with open(path) as f:
                    self.idx2word = self.unstring_ids(json.load(f))
            if filename.endswith('idx2tag.json'):
                with open(path) as f:
                    self.idx2tag = self.unstring_ids(json.load(f))
        return df

    def get_data(self,train_folders,isLoading = False):
        """
        All-purpose function to get data.
        isLoading: train_folder is SINGLE path to dir that contains .csv, dictionaries.
        !isLoading: rain_folders is LIST of paths to dirs that contain i2b2 data 
        """
        if not isLoading:
            _, t_array,c_array,labels = self.process_data(train_folders)
            self.create_vocab_dict()
            self.create_label_dict()
            df = self.convert_to_df(t_array,c_array,labels)
            X, y = self.create_train_set(df,isLoading) # modifies df, which is why it comes before sav
            self.save_processed_data(df)
        else:
            df = self.load_processed_data(train_folders)
            X,y = self.create_train_set(df,isLoading) # no modification to df in loading case
        print("Preprocessing complete.")
        return X, y, df