import tensorflow as tf
import numpy as np
from preprocess import PreProcessor

class BaselineModel(tf.keras.Model):
    def __init__(self,vocab_size,tag_size,max_len):
        super(BaselineModel,self).__init__()
        self.vocab_size =  vocab_size + 1 #add 1 because of weird problem with embedding lookup. only happens on large data. CPU/GPU related I think
        self.tag_size = tag_size
        self.max_len = max_len
        self.embedding_size = 64
        self.rnn_size = 128
        self.title = "baseline-rnn"

        self.E = tf.Variable(tf.random.normal([self.vocab_size,self.embedding_size],stddev = 0.1, dtype= tf.float32))
        self.rnn = tf.keras.layers.GRU(units= self.rnn_size, return_sequences = True)
        self.d1 = tf.keras.layers.TimeDistributed(tf.keras.layers.Dense(self.tag_size, activation = 'softmax'))

    @tf.function
    def call(self,inputs):
        """
        Inputs: (batch_size, max_len)
        Output: (batch_size, max_len, tag_size) 
        """
        #print("Input: ",inputs)
        embeddings = tf.nn.embedding_lookup(self.E,inputs) # (batch_size, max_len, embedding_size)
        outputs = self.rnn(embeddings) # (batch_size, max_len, rnn_size)
        predictions = self.d1(outputs) # (batch_size, max_len, tag_size)
        return predictions

    def loss(self,prbs,labels):
        return tf.reduce_sum(tf.keras.losses.sparse_categorical_crossentropy(labels, prbs))
