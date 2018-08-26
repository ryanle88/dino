import logging

from scipy import sparse
from sklearn.externals import joblib

from dino.environ import GNEnvironment
from dino.utils.decorators import timeit

__author__ = 'Oscar Eriksson <oscar.eriks@gmail.com>'

logger = logging.getLogger(__name__)


class SpamClassifier(object):
    def __init__(self, env: GNEnvironment):
        logger.info('loading TF-IDF and PCA transformers...')
        self.tfidf_char = joblib.load('transformer_1a.pkl')
        self.tfidf_word = joblib.load('transformer_1b.pkl')
        self.pca = joblib.load('transformer_2.pkl')

        logger.info('loading models...')
        self.xgb = joblib.load('classifier_1.pkl')
        self.rfc = joblib.load('classifier_2.pkl')
        self.svc = joblib.load('classifier_3.pkl')

        self.env = env

    @timeit(logger, 'on_transform')
    def transform(self, x):
        x = sparse.hstack((self.tfidf_char.fit_transform(x), self.tfidf_word.fit_transform(x))).A
        return self.pca.transform(x)

    @timeit(logger, 'on_predict')
    def predict(self, x):
        y_hat = (
            self.xgb.predict_proba(x),
            self.rfc.predict_proba(x),
            self.svc.predict(x)
        )

        # if 2 out of 3 classifiers are at least 66% certain it's spam, classify it as such
        return 1 if sum(1 for e in y_hat if e > 0.66) >= 2 else 0, y_hat

    def is_spam(self, message) -> (bool, tuple):
        x = self.transform([message])
        return self.predict(x)