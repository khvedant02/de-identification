import tensorflow as tf
import numpy as np
import chars2vec as c2v

class BiLSTM_Chars(tf.keras.Model):
    """
    BiLSTM seq2seq.
    """
    def __init__(self,vocab_size,tag_size,max_len,idx2word: dict):
        super(BiLSTM_Chars,self).__init__()
        self.vocab_size =  vocab_size + 1 #add 1 because of weird problem with embedding lookup. only happens on large data. CPU/GPU related I think
        self.tag_size = tag_size
        self.max_len = max_len
        self.embedding_size = 50
        self.rnn_size = 64
        self.title = "bi-lstm-chars"
        self.idx2word = idx2word
        self.c2v_model = c2v.load_model('eng_50')

        self.E = tf.Variable(tf.random.normal([self.vocab_size,self.embedding_size],stddev = 0.1, dtype= tf.float32))
        self.bi_lstm = tf.keras.layers.Bidirectional(tf.keras.layers.LSTM(self.rnn_size, return_sequences = True)) # automatically sets backward layer to be identical to forward layer
        self.d1 = tf.keras.layers.TimeDistributed(tf.keras.layers.Dense(self.tag_size, activation = 'softmax')) # softmax over tags for each word

    @tf.function(experimental_relax_shapes=True)
    def call(self,inputs, char_embeddings):
        """
        Inputs: (batch_size, max_len)
        Output: (batch_size, max_len, tag_size) 
        """
        embeddings = tf.nn.embedding_lookup(self.E,inputs) # (batch_size, max_len, embedding_size)
        embeddings = tf.concat([embeddings,char_embeddings],axis=2) # (batch_size, max_len, embedding_size + 50)
        # print(embeddings.shape)
        outputs = self.bi_lstm(embeddings) # (batch_size, max_len, 2*rnn_size)
        predictions = self.d1(outputs) # (batch_size, max_len, tag_size)
        return predictions

    def loss(self,prbs,labels):
        loss = tf.keras.losses.sparse_categorical_crossentropy(labels, prbs)
        mask = tf.cast(tf.not_equal(labels, 0), tf.float32)
        loss = tf.multiply(loss, mask)
        return tf.reduce_sum(loss)

    def predict(self,inputs, words = None):
        np_input = inputs.numpy()
        if words is None:
            words = [[self.idx2word[val] for val in row] for row in np_input]
            words = np.array(words).flatten() # chars2vec needs list of string
        else: 
            words = words.flatten()
            words = words.astype('str')
        char_embeddings = self.c2v_model.vectorize_words(words)
        char_embeddings = tf.reshape(char_embeddings, [1,-1,50])
        probs = self.call(inputs,char_embeddings)
        mle_output = tf.argmax(probs,axis=2).numpy().flatten()
        return mle_output

