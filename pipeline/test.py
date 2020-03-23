from sklearn.utils import shuffle
import tensorflow as tf
from .visualization import sample_output, sample_output_CRF, fancy_print, loss_plot
from .metrics import accuracy_function
from src.converter import bio_to_i2d2, get_label_positions
import xml.etree.ElementTree as ET
from src.preprocess import df_to_train_set
import os

PAD_IDX = 0
UNK_IDX = NON_PHI_IDX = 1

def test_vanilla(model, test_inputs, test_labels, pp = None, manager = None):
    n = len(test_inputs)
    test_batch_size = 32
    X = test_inputs
    y = test_labels
    total_seen = total_correct = 0
    for i in range(0,n,test_batch_size):
        input_batch = X[i:i+test_batch_size]
        output_batch = y[i:i+test_batch_size]
        
        probs = model(input_batch) # bsz x max_len x tag_size
        mask = output_batch != PAD_IDX
        num_predictions = tf.reduce_sum(tf.cast(mask,tf.float32))
        accuracy = accuracy_function(probs,output_batch,mask)

        total_seen += num_predictions
        total_correct += num_predictions*accuracy

    print("Per symbol accuracy: %.3f" % float(total_correct/total_seen))

def test_to_i2d2(model,test_df,pp,checkpoint = None,manager= None):
    """
    Predicts the PHI for all the documents in a DataFrame. Writes them to evaluation_data in i2b2 format.
    """
    cwd = os.getcwd()
    print(cwd)

    if checkpoint is not None and manager is not None:
        print("Loading checkpoint...")
        checkpoint.restore(manager.latest_checkpoint)

    unique_docids = test_df["docid"].unique()
    for docid in unique_docids:
        print("Doc ID: ",docid)
        tree = ET.parse("../data/raw/testing-PHI-Gold-fixed/" + docid + ".xml") # must pass entire path
        root = tree.getroot()
        note = root.find('TEXT').text
        predictions, doc_df = predict_document(model,docid,test_df)
        doc_labels = get_label_positions(predictions,pp.idx2tag)
        xml_doc = bio_to_i2d2(doc_df,doc_labels,note)
        ET.ElementTree(xml_doc).write("../evaluation_data/" + model.title + "/"+ docid+".xml")

def predict_document(model,docid,df):
    """
    Given a model, predict the PHI for all the sentences in docid (docid must exist in df)
    df contains all sentences of docid.
    """
    unique_docids = df["docid"].unique()
    assert docid in unique_docids, "DocID not in DataFrame"
    doc_df = df.groupby(by="docid").get_group(docid) # dataframe
    # print(doc_df)
    X,_ = df_to_train_set(doc_df,True)
    predictions = tf.argmax(model(X),axis=2).numpy()
    return predictions, doc_df



        
        