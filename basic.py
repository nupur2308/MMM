import dash
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output, State
import plotly.graph_objs as go
import base64
import datetime
from dash.exceptions import PreventUpdate

import pandas as pd
import numpy as np

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from sklearn.linear_model import Ridge, Lasso
from sklearn.metrics import mean_squared_error as mse
from sklearn.pipeline import Pipeline
from sklearn.model_selection import cross_val_score
from sklearn.model_selection import cross_validate
from sklearn.model_selection import GridSearchCV

app = dash.Dash()

df = pd.read_csv('Media variables 2021-11-18.csv',index_col =0)
df.index = pd.to_datetime(df.index)

features = df.columns

def empty_plot(label_annotation):
    '''
    Returns an empty plot with a centered text.
    '''

    trace1 = go.Scatter(
        x=[],
        y=[]
    )

    data = [trace1]

    layout = go.Layout(
        showlegend=False,
        xaxis=dict(
            autorange=True,
            showgrid=False,
            zeroline=False,
            showline=False,
            ticks='',
            showticklabels=False
        ),
        yaxis=dict(
            autorange=True,
            showgrid=False,
            zeroline=False,
            showline=False,
            ticks='',
            showticklabels=False
        ),
        annotations=[
            dict(
                x=0,
                y=0,
                xref='x',
                yref='y',
                text=label_annotation,
                showarrow=True,
                arrowhead=7,
                ax=0,
                ay=0
            )
        ]
    )

    fig = go.Figure(data=data, layout=layout)
    # END
    return fig

app.layout = html.Div([
        html.H1('Data Exploration'),
        html.Div([
            dcc.Dropdown(
                id='xaxis',
                options=[{'label': i.title(), 'value': i} for i in features],
                value='FAA Lead Form Impressions'
            )
        ],
        style={'width': '48%', 'display': 'inline-block'}),

        html.Div([
            dcc.Dropdown(
                id='yaxis',
                options=[{'label': i.title(), 'value': i} for i in features],
                value='Search-National Brand'
            )
        ],style={'width': '48%', 'float': 'right', 'display': 'inline-block'}),

    dcc.Graph(id='feature-graphic'),
    html.H1('Model Settings'),
    html.P('Select the output variable and model date range'),
    html.Div([
        dcc.Dropdown(
            id='yvar',
            options=[{'label': i.title(), 'value': i} for i in features],
            value='FAA Lead Form Impressions'
        )
    ],
    style={'width': '48%', 'display': 'inline-block'}),
    html.Div([
        dcc.DatePickerRange(
        id='my-date-picker-range',
        min_date_allowed=min(df.index),
        max_date_allowed=max(df.index),
        initial_visible_month=datetime.date(2018, 10, 22),
        end_date=datetime.date(2021, 6, 28)
        )
    ], style = {'marginBottom':'5px'}),
    html.Button('Build Model', id='submit-val', n_clicks=0, style = {'padding':'5px'}),
    html.H1('Model Validation'),
    html.Div([
        html.H4('Training Fit'),
        html.P(id='rmse-train'),
        dcc.Graph(id='fit-train')
    ],
    style={'width': '100%', 'display': 'inline-block'}),
    html.Div([
        html.H4('Test Fit'),
        html.P(id='rmse-test'),
        dcc.Graph(id='fit-test')
    ],
    style={'width': '100%', 'display': 'inline-block'}),
    html.H1('Model Contributions'),
    html.Div([
        dcc.Graph(id='all_contr'),
        dcc.Graph(id='WoW_contr')
    ],
    style={'width': '100%', 'display': 'inline-block'})
], style={'padding':10,'fontFamily':'helvetica'})

@app.callback(
    Output('feature-graphic', 'figure'),
    [Input('xaxis', 'value'),
     Input('yaxis', 'value')])

def update_graph(xaxis_name, yaxis_name):
    return {
        'data': [go.Scatter(
            x=df[xaxis_name],
            y=df[yaxis_name],
            mode='markers',
            marker={
                'size': 15,
                'opacity': 0.5,
                'line': {'width': 0.5, 'color': 'white'}
            }
        )],
        'layout': go.Layout(
            xaxis={'title': xaxis_name.title()},
            yaxis={'title': yaxis_name.title()},
            margin={'l': 40, 'b': 40, 't': 10, 'r': 0},
            hovermode='closest'
        )
    }

def rmse(a,p):
    return np.sqrt(mse(a,p))

def build_model(yvar,start_date,end_date):
    xvar = features[~features.str.contains(yvar)]
    media = df.loc[:,xvar]
    end_formatted = datetime.datetime.strptime(end_date, "%Y-%m-%d")
    X = np.array(media.loc[start_date:end_date])
    y = np.array(df.loc[start_date:end_date][yvar])

    X_test = np.array(media.loc[end_formatted+datetime.timedelta(days=7):max(media.index)])
    y_test = np.array(df.loc[end_formatted+datetime.timedelta(days=7):max(df.index)][yvar])


    ## Model Build and Fit
    param_range_lasso = {'lreg__alpha':[0.0001, 0.001, 0.01, 0.1, 1.0, 10.0, 100.0, 1000.0]}

    pipe_lr = Pipeline([
        ('sc',MinMaxScaler()),
        ('lreg',Lasso(tol=0.1))
        ])

    LR = GridSearchCV(estimator = pipe_lr,
                  param_grid = param_range_lasso,
                  scoring = 'neg_mean_squared_error',
                  n_jobs = -1,
                  cv = 10)

    LR.fit(X,y)

    ## Model Validation

    #### Training validation
    trainp = LR.best_estimator_.predict(X)
    trainy = y
    train_rmse = np.sqrt(-LR.best_score_)

    #### Testing validation
    testp = LR.best_estimator_.predict(X_test)
    testy = y_test
    test_rmse = rmse(testy,testp)

    ## Getting Contributions

    sc = MinMaxScaler()
    X_scaled = sc.fit(X).transform(X)
    lcoef = LR.best_estimator_['lreg'].coef_
    wow_contr = lcoef * X_scaled
    media_contr = pd.DataFrame(wow_contr,columns = xvar).set_index(df[start_date:end_date].index)
    intercept = LR.best_estimator_['lreg'].intercept_
    base_contr = pd.DataFrame([intercept]*X.shape[0], columns = ["Base"],index =df[start_date:end_date].index)
    contr_table = media_contr.join(base_contr)

    return train_rmse, trainp, trainy, test_rmse, testp, testy, contr_table


@app.callback([
    Output('fit-train', 'figure'),
    Output('fit-test', 'figure'),
    Output('rmse-train','children'),
    Output('rmse-test','children'),
    Output('all_contr', 'figure')
    ],
    [Input('submit-val','n_clicks')],
    [State('yvar','value'),
    State('my-date-picker-range','start_date'),
    State('my-date-picker-range','end_date')])

def update_output(n_clicks, yvar, start_date, end_date):
    train_rmse, trainp, trainy, test_rmse, testp, testy, contr_table = build_model(yvar,start_date,end_date)

    trace1 = go.Scatter(
            x = df.loc[start_date:end_date].index,
            y = trainy,
            mode = 'markers+lines',
            name = 'training set, actuals'
            )
    trace2 = go.Scatter(
            x = df.loc[start_date:end_date].index,
            y = trainp,
            mode = 'markers+lines',
            name = 'training set, predictions'
            )
    fig_1 = go.Figure(
                    data = [
                        trace1, trace2
                            ],
                        layout = go.Layout(
                                    xaxis= {'title': 'Weeks'},
                                    yaxis = {'title': yvar}
                                    )
                        )


    trace3 = go.Scatter(
            x = df.loc[end_date:max(df.index)].index,
            y = testy,
            mode = 'markers+lines',
            name = 'test set, actuals'
            )
    trace4 = go.Scatter(
            x = df.loc[end_date:max(df.index)].index,
            y = testp,
            mode = 'markers+lines',
            name = 'test set, predictions'
            )

    fig_2 = go.Figure(
                    data = [
                        trace3, trace4
                            ],
                        layout = go.Layout(
                                    xaxis= {'title': 'Weeks'},
                                    yaxis = {'title': yvar}
                                    )
                        )

    tr_rmse = 'RMSE: '+ str(np.around(train_rmse,2))
    te_rmse = 'RMSE: ' + str(np.around(test_rmse,2))

    contr_sum = pd.DataFrame(contr_table.sum(axis=0),columns = ["total"])

    fig_3  = go.Figure(
                        data=
                            [go.Bar(
                                x=contr_sum.index.tolist(),
                                y=contr_sum['total'].tolist()
                            )],

                        layout=go.Layout(
                                    xaxis = {'title':'Variables',
                                            'tickangle':-45
                                            },
                                    yaxis = {'title':'Contribution'},
                                    margin = {'b':150,'l':150}
                                        )
                        )


    if n_clicks <1:
        return empty_plot('Nothing to Display'), empty_plot('Nothing to Display'),"", "", empty_plot('Nothing to Display')
    else:
        return fig_1, fig_2, tr_rmse, te_rmse, fig_3



if __name__ == '__main__':
    app.run_server()
