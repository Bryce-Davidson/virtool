/**
 * @license
 * The MIT License (MIT)
 * Copyright 2015 Government of Canada
 *
 * @author
 * Ian Boyes
 *
 * exports IsolateList
 */

'use strict';

var React = require('react');
var ReactDOM = require('react-dom');
var FlipMove = require('react-flip-move');
var ListGroup = require('react-bootstrap/lib/ListGroup');
var ListGroupItem = require('virtool/js/components/Base/PushListGroupItem.jsx');
var Badge = require('react-bootstrap/lib/Badge');

var Icon = require('virtool/js/components/Base/Icon.jsx');
var Scroll = require('virtool/js/components/Base/Scroll.jsx');
var PushButton = require('virtool/js/components/Base/PushButton.jsx');

var Isolate = require('./Isolate.jsx');
var IsolateAdd = require('./IsolateAdd.jsx');

/**
 * A component that lists the isolates associated with a virus as Isolate components.
 *
 * @class
 */
var IsolateList = React.createClass({

    propTypes: {
        // An array of isolates documents.
        data: React.PropTypes.array.isRequired,

        activeIsolateId: React.PropTypes.string,
        restrictSourceTypes: React.PropTypes.bool,
        allowedSourceTypes: React.PropTypes.array,

        // Function to call when the add button is clicked or the add form is dismissed.
        toggleAdding: React.PropTypes.func
    },

    getInitialState: function () {
        return {
            restrictSourceTypes: this.props.settings.get('restrict_source_types'),
            allowedSourceTypes: this.props.settings.get('allowed_source_types')
        };
    },

    componentDidMount: function () {
        this.props.settings.on('change', this.update);
        ReactDOM.findDOMNode(this.refs.flip).addEventListener("resize", this.updateScroll);
    },

    componentWillUnmount: function () {
        this.props.settings.off('change', this.update);
        ReactDOM.findDOMNode(this.refs.flip).removeEventListener("resize", this.updateScroll);
    },

    /**
     * Update the component with new restricted source type settings. Triggered by an update event from the settings
     * object.
     *
     * @func
     */
    update: function () {
        this.setState(this.getInitialState());
    },

    updateScroll: function () {
        this.refs.scroll.update();
    },

    render: function () {

        // Render each isolate as a selectable list item
        var isolateComponents = this.props.data.map(function (isolate) {
            var props = {
                key: isolate.isolate_id,
                virusId: this.props.virusId,
                isolateId: isolate.isolate_id,
                sourceName: isolate.source_name,
                sourceType: isolate.source_type,
                default: isolate.default,

                active: isolate.isolate_id === this.props.activeIsolateId,
                selectIsolate: this.props.selectIsolate,

                canModify: this.props.canModify
            };

            return (
                <Isolate
                    {...props}
                    {...this.state}
                />
            );
        }, this);

        // The final list item can display either an 'New Isolate' button or a form for adding a new isolate
        var lastComponent;

        // If the 'addingIsolate' prop is true, render the form. Otherwise display a button to open the form.
        if (this.props.canModify) {
            lastComponent = (
                <IsolateAdd
                    key="last"
                    virusId={this.props.virusId}
                    default={this.props.data.length === 0}
                    active={this.props.activeIsolateId === 'new'}
                    toggleAdding={this.props.toggleAdding}
                    {...this.state}
                    canModify={this.props.canModify}
                    updateScroll={this.updateScroll}
                />
            );
        }

        if (!this.props.canModify && isolateComponents.length === 0) {
            lastComponent = (
                <ListGroupItem ref="last" key="last">
                    <div className='text-center'>
                        <Icon name='info' /> No isolates found.
                    </div>
                </ListGroupItem>
            );
        }

        var flipProps = {
            typeName: "div",
            className: "list-group",
            enterAnimation: "fade",
            leaveAnimation: false,
            duration: 150
        };

        return (
            <div>
                <h5 ref="header">
                    <strong><Icon name='lab' /> Isolates</strong> <Badge>{this.props.data.length}</Badge>
                </h5>
                <Scroll ref="scroll" style={{marginBottom: "15px"}}>
                    <FlipMove ref="flip" {...flipProps} style={{marginBottom: 0, marginRight: "10px"}} onFinishAll={this.updateScroll}>
                        {isolateComponents}
                        {lastComponent}
                    </FlipMove>
                </Scroll>
            </div>
        );
    }

});

module.exports = IsolateList;