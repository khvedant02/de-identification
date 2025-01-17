import tensorflow as tf
import tensorflow_addons as tfa
import numpy as np

class BiLSTM_CRF(tf.keras.Model):
    """
    CRF stacked on top of BILSTM.
    """
    def __init__(self,vocab_size,tag_size,max_len):
        super(BiLSTM_CRF,self).__init__()
        self.vocab_size =  vocab_size + 1 #add 1 because of weird problem with embedding lookup. only happens on large data. CPU/GPU related I think
        self.tag_size = tag_size
        self.max_len = max_len
        self.embedding_size = 64
        self.rnn_size = 128
        self.title = "bi-lstm-crf"
        print("Num GPUs Available: ", len(tf.config.experimental.list_physical_devices('GPU')))

        self.transition_params = tf.random.uniform((self.tag_size,self.tag_size)) # for CRF

        self.E = tf.Variable(tf.random.normal([self.vocab_size,self.embedding_size],stddev = 0.1, dtype= tf.float32)) # embeddings
        self.bi_lstm = tf.keras.layers.Bidirectional(tf.keras.layers.LSTM(self.rnn_size, return_sequences = True)) # automatically sets backward layer to be identical to forward layer
        self.d1 = tf.keras.layers.TimeDistributed(tf.keras.layers.Dense(self.tag_size)) # logits over tags for each word


    @tf.function
    def call(self,inputs,labels):
        """
        Inputs: (batch_size, max_len)
        Output: (batch_size, max_len, tag_size) 
        """
        embeddings = tf.nn.embedding_lookup(self.E,inputs) # (batch_size, max_len, embedding_size)
        outputs = self.bi_lstm(embeddings) # (batch_size, max_len, 2*rnn_size)
        logits = self.d1(outputs) # (batch_size, max_len, tag_size)

        mask = tf.cast(tf.not_equal(labels, 0), tf.float32)
        true_lengths = tf.reduce_sum(mask,axis = 1) # likelihood should ignore masks
        log_likelihood, transition = tfa.text.crf_log_likelihood(logits,labels,true_lengths,self.transition_params)
        return log_likelihood, transition

    def loss(self,log_likelihood):
        return tf.reduce_mean(-1*log_likelihood)

    def predict(self,inputs):
        """
        Inputs: (batch_size, max_len)
        Output: (batch_size, max_len, tag_size)
        Uses virterbi algorithm to find most likely sequence of states (labels). 
        """
        embeddings = tf.nn.embedding_lookup(self.E,inputs) # (batch_size, max_len, embedding_size)
        outputs = self.bi_lstm(embeddings) # (batch_size, max_len, 2*rnn_size)
        logits = self.d1(outputs) # (batch_size, max_len, tag_size)

        pre_seqs = []
        for score in logits:
            pre_seq, _ = tfa.text.viterbi_decode(score[:], self.transition_params)
            pre_seqs.append(pre_seq)
        return np.array(pre_seqs).flatten()

        

