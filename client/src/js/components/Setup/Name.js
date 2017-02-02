/**
 * @license
 * The MIT License (MIT)
 * Copyright 2015 Government of Canada
 *
 * @author
 * Ian Boyes
 *
 * @exports SetupDatabaseName
 */

import React from "react";
import { ListGroup } from "react-bootstrap";
import { Input, Icon, Button, ListGroupItem } from "virtool/js/components/Base"
import { postJSON } from "virtool/js/utils";

const Name = (props) => (
    <ListGroupItem onFocus={props.onFocus} onClick={() => props.updateName(props.name)} active={props.active}>
        <Icon name="database" /> {props.name}
    </ListGroupItem>
);

Name.propTypes = {
    name: React.PropTypes.string.isRequired,
    active: React.PropTypes.bool.isRequired,
    updateName: React.PropTypes.func.isRequired,
    onFocus: React.PropTypes.func.isRequired
};

export default class SetupDatabaseName extends React.Component {

    constructor (props) {
        super(props);
        this.state = {
            name: this.props.name,
            pending: false
        };
    }

    static propTypes = {
        host: React.PropTypes.string,
        port: React.PropTypes.number,
        names: React.PropTypes.arrayOf(React.PropTypes.string),
        name: React.PropTypes.string.isRequired,
        updateSetup: React.PropTypes.func.isRequired,
        checkedName: React.PropTypes.func
    };

    componentDidMount () {
        this.inputNode.focus();
    }

    updateName = (name) => this.setState({name: name.toLowerCase()});

    handleRadioFocus = () => this.inputNode.focus();

    handleSubmit = (event) => {
        event.preventDefault();

        const args = {
            host: this.props.host,
            port: this.props.port,
            name: this.state.name,
            operation: "check_db"
        };

        postJSON("/", args, (data) => {
            this.setState({pending: false}, () => {
                if (!data.error) {
                    data.name = this.state.name;
                    this.props.checkedName(data);
                }
            });
        });
    };

    render () {

        let existingDatabases;

        if (this.props.names.length) {
            existingDatabases = this.props.names.map((name, index) =>
                <Name
                    key={index}
                    name={name}
                    active={name === this.state.name}
                    updateName={this.updateName}
                    onFocus={this.handleRadioFocus}
                />
            );
        } else {
            existingDatabases = (
                <ListGroupItem>
                    <Icon name="info" /> None found.
                </ListGroupItem>
            );
        }

        return (
            <form onSubmit={this.handleSubmit}>
                <Input
                    ref={(node) => {this.inputNode = node}}
                    type="text"
                    label="Database Name"
                    onChange={(event) => this.updateName(event.target.value)}
                    spellCheck={false}
                    value={this.state.name}
                />

                <h5><strong>Existing Databases</strong></h5>
                <ListGroup>
                    {existingDatabases}
                </ListGroup>

                <Button bsStyle="primary" type="submit" disabled={!this.state.name} pullRight>
                    <Icon name="floppy" pending={this.state.pending} /> Save
                </Button>
            </form>
        );
    }

}